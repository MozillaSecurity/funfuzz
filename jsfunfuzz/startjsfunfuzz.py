#!/usr/bin/env python
#
#/* ***** BEGIN LICENSE BLOCK	****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is jsfunfuzz.
#
# The Initial Developer of the Original Code is
# Gary Kwong.
# Portions created by the Initial Developer are Copyright (C) 2008-2010
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# * ***** END LICENSE BLOCK	****	/

import os
import platform
import shutil
import subprocess
import sys
import time

from random import randint
from fnStartjsfunfuzz import *

path0 = os.path.dirname(sys.argv[0])
path2 = os.path.abspath(os.path.join(path0, "..", "js-autobisect"))
sys.path.append(path2)
import autoBisect

def main():

    # Variables
    verbose = False
    selfTests = True
    multiTimedRunTimeout = '10'

    if os.name != 'nt' and os.uname()[4] == 'armv7l':
        if os.uname()[1] == 'tegra-ubuntu':
            multiTimedRunTimeout = '180'
        else:
            multiTimedRunTimeout = '600'

    traceJit = False  # Activate support for tracing JIT in configure.
    jsJitSwitch = False  # Activate tracing JIT fuzzing here.
    methodJit = True  # Activate support for method JIT in configure.
    methodJitSwitch = True  # Activate JIT fuzzing here.
    methodJitAllSwitch = True  # turn on -a
    profileJitSwitch = False  # turn on -p
    debugJitSwitch = True  # turn on -d

    # This produces "can't change object's extensibility" messages in a lot of jsfunfuzz testcases.
    deepFreezeGlobalObjPrototypeSwitch = False  # turn on -P
    # Pymake is activated on Windows platforms by default, for default tip only.
    usePymake = True if os.name == 'nt' else False

    jsCompareJITSwitch = True
    # Disable compareJIT if methodJit support is disabled in configure.
    if not methodJitSwitch:
        jsCompareJITSwitch = False
    # Disable compareJIT for 1.9.1 and 1.9.2 branches.
    if sys.argv[3] == '191' or sys.argv[3] == '192':
        jsCompareJITSwitch = False

    # Activate to True to --enable-threadsafe for a multithreaded js shell.
    # Make sure NSPR is first installed! (Use `make` instead of `gmake`)
    #   https://developer.mozilla.org/en/NSPR_build_instructions
    threadsafe = False

    if os.name != 'nt' and (os.uname()[0] == "Linux" or os.uname()[0] == "Darwin"):
        # Enable creation of coredumps.
        verboseDump('Setting ulimit -c to unlimited..')
        subprocess.call(['ulimit -c unlimited'], shell=True)
        if os.uname()[0] == "Linux":
            # Only allow one process to create a coredump at a time.
            subprocess.call(['echo 1 | sudo tee /proc/sys/kernel/core_uses_pid'], shell=True)


    branchSuppList = []
    # Add supported branches here.
    branchSuppList.append('191')
    branchSuppList.append('192')
    # Uncomment this and add 2.0's js-known dir, then get immediate 2.0 support
    #branchSuppList.append('20')
    #201support
    #branchSuppList.append('201')
    branchSuppList.append('mc')
    branchSuppList.append('tm')
    branchSuppList.append('jm')
    branchSuppList.append('im')
    branchSuppList.append('mi')
    branchSuppList.append('larch')

    branchSupp = '['
    branchSupp += '|'.join('%s' % n for n in branchSuppList)
    branchSupp += ']'

    # There should be a minimum of 4 command-line parameters.
    if len(sys.argv) < 4:
        error(branchSupp)
        raise Exception('Too little command-line parameters.')

    # Check supported operating systems.
    osCheck()
    if (sys.argv[1] == '32') and (os.name == 'posix'):
        # For the Mac, 32-bit js shells have only been tested on i386.
        if (os.uname()[0] == 'Darwin' and os.uname()[4] != 'i386'):
            raise Exception('32-bit compilation is not supported on non-i386 Darwin platforms.')
    elif (sys.argv[1] == '64'):
        # 64-bit js shells have only been tested on Linux x86_64 (AMD64) platforms.
        if os.name != 'nt' and os.uname()[0] == 'Linux' and os.uname()[4] != 'x86_64':
            raise Exception('64-bit compilation is not supported on non-x86_64 Linux platforms.')
        if (sys.argv[3] == '191'):
            raise Exception('64-bit compilation is not supported on 1.9.1 branch.')


    # Accept 32-bit and 64-bit parameters only.
    if (sys.argv[1] == '32') or (sys.argv[1] == '64'):
        archNum = sys.argv[1]
    else:
        error(branchSupp)
        print '\nYour archNum variable is "' + sys.argv[1] + '".',
        raise Exception('archNum not among list of [32|64].')

    # Accept dbg and opt parameters for compileType only.
    if (sys.argv[2] == 'dbg') or (sys.argv[2] == 'opt'):
        compileType = sys.argv[2]
    else:
        error(branchSupp)
        print '\nYour compileType variable is "' + sys.argv[2] + '".',
        print 'Choose only from [dbg|opt].\n'
        exceptionBadCompileType()

    # Accept appropriate parameters for branchType.
    branchType = ''
    for brnch in branchSuppList:
        if (brnch == sys.argv[3]):
            branchType = sys.argv[3]
    if branchType == '':
        error(branchSupp)
        print '\nYour branchType variable is "' + sys.argv[3] + '".',
        print 'Choose only from %s.\n' % branchSupp
        exceptionBadBranchType()

    valgrindSupport = False
    if (os.name == 'posix'):
        if (len(sys.argv) == 5 and sys.argv[4] == 'valgrind') or \
            (len(sys.argv) == 7 and sys.argv[6] == 'valgrind') or \
            (len(sys.argv) == 9 and sys.argv[8] == 'valgrind'):
            if os.uname()[0] == 'Linux':
                valgrindSupport = True
                # compareJIT is too slow..
                jsCompareJITSwitch = False  # Turn off compareJIT when in Valgrind.
                multiTimedRunTimeout = '300'  # Increase timeout to 300 in Valgrind.
            elif os.uname()[0] == 'Darwin':
                # Technically we could enable Valgrind for Leopard only, but disable for SL.
                # A better solution would be to wait till Valgrind on MacPorts supports both.
                raise Exception("Valgrind on MacPorts for Snow Leopard isn't really ready..")
            else:
                exceptionBadOs()


    repoDict = {}
    pathSeparator = os.sep
    # Definitions of the different repository and fuzzing locations.
    # Remember to normalize paths to counter forward/backward slash issues on Windows.
    repoDict['fuzzing'] = os.path.normpath(os.path.expanduser(os.path.join('~', 'fuzzing'))) + pathSeparator
    repoDict['191'] = os.path.normpath(os.path.expanduser(os.path.join('~', 'mozilla-1.9.1'))) + pathSeparator
    repoDict['192'] = os.path.normpath(os.path.expanduser(os.path.join('~', 'mozilla-1.9.2'))) + pathSeparator
    repoDict['20'] = os.path.normpath(os.path.expanduser(os.path.join('~', 'mozilla-2.0'))) + pathSeparator
    #201support
    #repoDict['201'] = os.path.normpath(os.path.expanduser(os.path.join('~', 'mozilla-2.0.1'))) + pathSeparator
    repoDict['mc'] = os.path.normpath(os.path.expanduser(os.path.join('~', 'mozilla-central'))) + pathSeparator
    repoDict['tm'] = os.path.normpath(os.path.expanduser(os.path.join('~', 'tracemonkey'))) + pathSeparator
    repoDict['jm'] = os.path.normpath(os.path.expanduser(os.path.join('~', 'jaegermonkey'))) + pathSeparator
    repoDict['im'] = os.path.normpath(os.path.expanduser(os.path.join('~', 'ionmonkey'))) + pathSeparator
    repoDict['mi'] = os.path.normpath(os.path.expanduser(os.path.join('~', 'mozilla-inbound'))) + pathSeparator
    repoDict['larch'] = os.path.normpath(os.path.expanduser(os.path.join('~', 'larch'))) + pathSeparator
    # Start of fuzzing directory, does not need pathSeparator at the end.
    fuzzPathStart = os.path.normpath(os.path.expanduser(os.path.join('~', 'Desktop', 'jsfunfuzz-')))
    if os.name == 'nt' and 'Windows-XP' in platform.platform():
        raise Exception('Not supported on Windows XP.')
        # for repo in repoDict.keys():
            ## It is assumed that on WinXP, the corresponding directories are in the root folder.
            ## e.g. Instead of `~/tracemonkey/`, TM would be in `/tracemonkey/`.
            # repoDict[repo] = repoDict[repo][1:]
        # fuzzPathStart = '/jsfunfuzz-'  # Start of fuzzing directory

    if verbose:
        for repo in repoDict.keys():
            verboseDump('The directory for the "' + repo + '" repository is "' + repoDict[repo] + '"')

    fuzzPath = fuzzPathStart + compileType + '-' + archNum + '-' + branchType + pathSeparator
    if 'Windows-XP' not in platform.platform():
        fuzzPath = os.path.expanduser(fuzzPath)  # Expand the ~ folder except on WinXP.

    # Save the current directory as a variable.
    currDir = os.getcwd()

    # Note and attach the numbers and hashes of the current changeset in the fuzzPath.
    if 'Windows-XP' not in platform.platform():
        try:
            os.chdir(os.path.expanduser(repoDict[branchType]))
        except OSError:
            raise Exception('The directory for "' + branchType + '" is not found.')
        (fuzzPath, onDefaultTip) = hgHashAddToFuzzPath(fuzzPath, currWorkingDir=os.path.expanduser(repoDict[branchType]))
        os.chdir(os.path.expanduser(currDir))
    else:
        try:
            os.chdir(repoDict[branchType])
        except OSError:
            raise Exception('The directory for "' + branchType + '" is not found.')
        (fuzzPath, onDefaultTip) = hgHashAddToFuzzPath(fuzzPath, currWorkingDir=repoDict[branchType])
        os.chdir(currDir)

    # Turn off pymake if not on default tip.
    if usePymake and not onDefaultTip:
        usePymake = False

    # Raise an exception if not on default tip on Windows.
    if os.name == 'nt' and not onDefaultTip:
        raise Exception('Only default tip is supported on Windows platforms for the moment.')

    # Create the fuzzing folder.
    try:
        # Rename directory if patches are applied, accept up to 2 patches.
        if len(sys.argv) >= 6 and (sys.argv[4] == 'patch' or sys.argv[6] == 'patch'):
            fuzzPath = os.path.join(fuzzPath, 'patched')
            verboseDump('Patched fuzzPath is: ' + fuzzPath)
        #os.makedirs(fuzzPath)
    except OSError:
        raise Exception("The fuzzing path at '" + fuzzPath + "' already exists!")


    # Copy the js tree to the fuzzPath.
    compilePath = os.path.join(fuzzPath, 'compilePath', 'js', 'src')
    cpJsTreeDir(repoDict[branchType], compilePath, 'jsSrcDir')
    if os.path.isdir(os.path.normpath(os.path.join(repoDict[branchType], 'js', 'public'))):
        cpJsTreeDir(repoDict[branchType], os.path.join(compilePath, '..', 'public'), 'jsPublicDir')
    if os.path.isdir(os.path.normpath(os.path.join(repoDict[branchType], 'mfbt'))):
        cpJsTreeDir(repoDict[branchType], os.path.join(compilePath, '..', '..', 'mfbt'), 'mfbtDir')
    os.chdir(compilePath)  # Change into compilation directory.


    # Only patch the gc() function if on default tip.
    # Update: this is no longer needed from m-c rev f0159088a7c3.
    if False and jsCompareJITSwitch and onDefaultTip:
        # This patch makes the gc() function return an empty string (consistently)
        # rather than returning some information about the gc heap.
        verboseDump('Patching the gc() function now.')
        if 'Windows-XP' not in platform.platform():
            # -F4 to switch the fuzz factor to 4 until we get an updated patch (might not work on old changesets) or a patch with less context.
            jsCompareJITCode = subprocess.call(['patch', '-p3', '-F4', '-i', os.path.normpath(repoDict['fuzzing']) + os.sep + os.path.join('jsfunfuzz', 'patchGC.diff')])
        else:
            # -F4 to switch the fuzz factor to 4 until we get an updated patch (might not work on old changesets) or a patch with less context.
            # We have to use `<` and `shell=True` here because of the drive letter of the path to patchGC.diff.
            # Python piping might be possible though slightly more complicated.
            jsCompareJITCode = subprocess.call(['patch -p3 -F4 < ' + os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('jsfunfuzz', 'patchGC.diff'))], shell=True)
        if (jsCompareJITCode == 1) or (jsCompareJITCode == 2):
            jsCompareJITCodeBool1 = str(raw_input('Was a previously applied patch detected? (y/n): '))
            if jsCompareJITCodeBool1 == ('y' or 'yes'):
                jsCompareJITCodeBool2 = str(raw_input('Did you assume -R? (y/n): '))
                if jsCompareJITCodeBool2 != ('n' or 'no'):
                    raise Exception('The patch for --comparejit should be patched.')
            else:
                raise Exception('Required js patch for --comparejit failed to patch.')
        verboseDump('Finished incorporating the gc() patch that is needed for compareJIT.')

    # Patch the codebase if specified, accept up to 2 patches.
    patchReturnCode = 0
    patchReturnCode2 = 0
    if len(sys.argv) < 8 and len(sys.argv) >= 6 and sys.argv[4] == 'patch':
        patchReturnCode = subprocess.call(['patch', '-p3', '-i', sys.argv[5]])
        verboseDump('Finished incorporating the first patch.')
    elif len(sys.argv) >= 8 and sys.argv[6] == 'patch':
        patchReturnCode = subprocess.call(['patch', '-p3', '-i', sys.argv[5]])
        verboseDump('Finished incorporating the first patch.')
        patchReturnCode2 = subprocess.call(['patch', '-p3', '-i', sys.argv[7]])
        verboseDump('Finished incorporating the second patch.')
    if (patchReturnCode == 1 or patchReturnCode2 == 1) or (patchReturnCode == 2 or patchReturnCode2 == 2):
        raise Exception('Patching failed.')

    # FIXME we should make startjsfunfuzz.py not rely on os.getcwdu(), instead run subprocess calls
    # with the required directory set. In short, stop jumping around directories.
    autoconfRun(compilePath)

    # Create objdirs within the compilePaths.
    objdir = os.path.join(compilePath, compileType + '-objdir')
    os.mkdir(objdir)
    # Compile the other shell.
    if compileType == 'dbg':
        objdir2 = os.path.join(compilePath, 'opt-objdir')
    elif compileType == 'opt':
        objdir2 = os.path.join(compilePath, 'dbg-objdir')
    os.mkdir(objdir2)
    os.chdir(objdir)

    # Compile the first binary.
    cfgJsBin(archNum, compileType, traceJit, methodJit,
                      valgrindSupport, threadsafe, os.path.join(compilePath, 'configure'), objdir)
    # No longer need `export SHELL` with latest MozillaBuild.
    #if usePymake and os.name == 'nt':
        ## This has to use `shell=True`.
        #subprocess.call(['export SHELL'], shell=True)  # See https://developer.mozilla.org/en/pymake

    # Compile and copy the first binary.
    jsShellName = compileCopy(archNum, compileType, branchType, usePymake, fuzzPath, objdir, valgrindSupport)
    # Change into compilePath/js/src/ for the second binary.
    os.chdir('../')

    # Test compilePath.
    verboseDump('This should be the compilePath/js/src:')
    verboseDump('%s\n' % os.getcwdu())
    if selfTests:
        if 'src' not in os.getcwdu():
            raise Exception('We are not in src.')

    # Re-run autoconf again.
    autoconfRun(compilePath)

    # Compile the other binary.
    # No need to assign jsShellName here, because we are not fuzzing this one.
    if compileType == 'dbg':
        os.chdir('opt-objdir')
        cfgJsBin(archNum, 'opt', traceJit, methodJit,
                          valgrindSupport, threadsafe,
                          os.path.join(compilePath, 'configure'), objdir2)
        compileCopy(archNum, 'opt', branchType, usePymake, fuzzPath, objdir2, valgrindSupport)
    elif compileType == 'opt':
        os.chdir('dbg-objdir')
        cfgJsBin(archNum, 'dbg', traceJit, methodJit,
                          valgrindSupport, threadsafe,
                          os.path.join(compilePath, 'configure'), objdir2)
        compileCopy(archNum, 'dbg', branchType, usePymake, fuzzPath, objdir2, valgrindSupport)


    os.chdir('../../../../')  # Change into fuzzPath directory.

    # Test fuzzPath.
    verboseDump('os.getcwdu() should be the fuzzPath:')
    verboseDump(os.getcwdu() + str(pathSeparator))
    verboseDump('fuzzPath is: %s\n' % fuzzPath)
    if selfTests:
        if os.name == 'posix': # temporarily disable this since this doesn't yet work with the new os.path.join stuff
            if fuzzPath != (os.getcwdu()):
                raise Exception('We are not in fuzzPath.')
        elif os.name == 'nt':
            pass  # temporarily disable this since this doesn't yet work with the new os.path.join stuff
            #if fuzzPath[1:] != (os.getcwdu() + '/')[3:]:  # Ignore drive letter.
                #raise Exception('We are not in fuzzPath.')

    # Copy over useful files that are updated in hg fuzzing branch.
    cpUsefulFiles(os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('jsfunfuzz', 'jsfunfuzz.js')))
    cpUsefulFiles(os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('jsfunfuzz', 'analysis.py')))
    cpUsefulFiles(os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('jsfunfuzz', 'findInterestingFiles.py')))
    cpUsefulFiles(os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('jsfunfuzz', 'runFindInterestingFiles.sh')))
    cpUsefulFiles(os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('jsfunfuzz', 'runFindInterestingFiles.py')))
    cpUsefulFiles(os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('jsfunfuzz', '4test.py')))


    jsknownDict = {}
    # Define the corresponding js-known directories.
    jsknownDict['191'] = os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('js-known', 'mozilla-1.9.1')) + pathSeparator
    jsknownDict['192'] = os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('js-known', 'mozilla-1.9.2')) + pathSeparator
    jsknownDict['20'] = os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('js-known', 'mozilla-2.0')) + pathSeparator
    #201support
    #jsknownDict['201'] = os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('js-known', 'mozilla-2.0.1')) + pathSeparator
    jsknownDict['mc'] = os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('js-known', 'mozilla-central')) + pathSeparator
    # For TM and JM, we use mozilla-central's js-known directories.
    jsknownDict['tm'] = os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('js-known', 'mozilla-central')) + pathSeparator
    jsknownDict['jm'] = os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('js-known', 'mozilla-central')) + pathSeparator
    jsknownDict['im'] = os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('js-known', 'mozilla-central')) + pathSeparator
    jsknownDict['mi'] = os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('js-known', 'mozilla-central')) + pathSeparator
    jsknownDict['larch'] = os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('js-known', 'mozilla-central')) + pathSeparator

    multiTimedRun = os.path.normpath(repoDict['fuzzing'] + os.sep + os.path.join('jsfunfuzz', 'multi_timed_run.py'))

    if jsJitSwitch:
        jsJit = ' -j '
    else:
        jsJit = ' '
    # FIXME: --random-flags can be done in a better way instead of appending here
    if jsCompareJITSwitch:
        jsCompareJIT = ' --comparejit --random-flags '
    else:
        jsCompareJIT = ' --random-flags '

    if branchType == 'jm':
        jsCompareJIT += '--repo=' + repoDict['jm'] + ' '
    if branchType == 'im':
        jsCompareJIT += '--repo=' + repoDict['im'] + ' '
    if branchType == 'mi':
        jsCompareJIT += '--repo=' + repoDict['mi'] + ' '
    if branchType == 'larch':
        jsCompareJIT += '--repo=' + repoDict['larch'] + ' '

    if methodJitSwitch:
        jsMethodJit = '-m -n '
        if methodJitAllSwitch:
            jsMethodJit = '-m -n -a '
    else:
        jsMethodJit = ''

    # FIXME: This can be done in a better way instead of appending to jsMethodJit
    if profileJitSwitch:
        jsMethodJit += '-p '
    if debugJitSwitch and branchType != 'im':
        jsMethodJit += '-d '
    if deepFreezeGlobalObjPrototypeSwitch:
        jsMethodJit += '-P '
    # TI has landed on m-c!
    #if branchType == 'jm':
    #    jsMethodJit += '-n '  # For type inference
    # Thanks to decoder and sstangl:
    # useful flag combinations are {{--ion -n, --ion, --ion-eager} x {--ion-regalloc=greedy, --ion-regalloc=lsra}}
    if branchType == 'im':
        # Actually these flags should be random within multi timed run, not in startjsfunfuzz
        #rndIntIM = randint(0,5)
        rndIntIM = 5  # start off with ion-eager. --random-flags might treat --ion -n as two flags, which should not be the case.
        if rndIntIM == 0:
            jsMethodJit += '--ion -n --ion-regalloc=greedy '
        elif rndIntIM == 1:
            jsMethodJit += '--ion --ion-regalloc=greedy '
        elif rndIntIM == 2:
            jsMethodJit += '--ion-eager --ion-regalloc=greedy '
        elif rndIntIM == 3:
            jsMethodJit += '--ion -n --ion-regalloc=lsra '
        elif rndIntIM == 4:
            jsMethodJit += '--ion --ion-regalloc=lsra '
        elif rndIntIM == 5:
            jsMethodJit += '--ion-eager --ion-regalloc=lsra '


    # Commands to simulate bash's `tee`.
    tee = subprocess.Popen(['tee', 'log-jsfunfuzz'], stdin=subprocess.PIPE)


    # Define fuzzing command with the required parameters.
    if 'Windows-XP' not in platform.platform():
        multiTimedRun = os.path.expanduser(multiTimedRun)
        jsknownDict[branchType] = os.path.expanduser(jsknownDict[branchType])
    fuzzCmd1 = 'python -u ' + multiTimedRun + jsCompareJIT
    if valgrindSupport:
        fuzzCmd1 = fuzzCmd1 + ' --valgrind'
    fuzzCmd = fuzzCmd1 + ' ' + multiTimedRunTimeout + ' ' + jsknownDict[branchType] + ' ' + jsShellName + jsJit + jsMethodJit

    verboseDump('jsShellName is: ' + jsShellName)
    verboseDump('fuzzPath + jsShellName is: ' + jsShellName)
    if os.name == 'nt':
        print('fuzzCmd is: ' + fuzzCmd.replace('\\', '\\\\') + '\n')
    else:
        print('fuzzCmd is: ' + fuzzCmd + '\n')


    # 32-bit or 64-bit verification test.
    if (os.name == 'posix'):
        if (os.uname()[0] == 'Linux') or (os.uname()[0] == 'Darwin'):
            assert archOfBinary(jsShellName) == archNum

    # Debug or optimized binary verification test.
    testDbgOrOptGivenACompileType(jsShellName, compileType)


    print '''
    ================================================
    !  Fuzzing %s %s %s js shell builds now  !
       DATE: %s
    ================================================
    ''' % (archNum + '-bit', compileType, branchType, time.asctime( time.localtime(time.time()) ))

    # Commands to simulate bash's `tee`.
    # Start fuzzing the newly compiled builds.
    subprocess.call(fuzzCmd, stdout=tee.stdin, shell=True)


# Run main when run as a script, this line means it will not be run as a module.
if __name__ == '__main__':
    main()

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
#
# Version History:
#
# April 2008 - 1.x:
#   Initial idea, previously called ./jsfunfuzz-moz18branch-start-intelmac
# June 2008 - 2.x:
#   Rewritten from scratch to support the new hg fuzzing branch.
# August 2008 - 3.0.x:
#   Rewritten from scratch again to support command-line inputs and consolidate
#   all existing jsfunfuzz bash scripts.
# September 2008 - 3.1.x:
# 	Support fuzzing v8 engine.
# December 2008 - 3.2.x:
#   Supports 1.9.1.x branch. Rip out 1.8.1.x code.
# January 2009 - 3.3.x:
#   Rework v8 support, add JavaScriptCore support.
# July 2009 - 4.x:
#   Python rewrite - only 1.9.1.x, 1.9.2.x and TM planned for support. 1.9.0.x
#   is becoming obsolete in 5.5 months, mozTrunk is rarely fuzzed in favour of
#   TM, JavaScriptCore doesn't feel like a significant competing engine,
#   and Safari uses its own Nitro engine. v8 might come later too.
# November 2009 - 5.x:
#   (version numbers are now obsolete - will no longer be added)
#   Add 32-bit and 64-bit compilation, patching support. Host of other
#   improvements. Now only supports 1.9.1.x, 1.9.2.x, TM and a future 1.9.3.x.
# February 2010:
#   Massive rewrite, reducing code by ~8%. Support Valgrind on Linux, 64-bit
#   Linux and Jaegermonkey. No longer supports 10.5.x, 32-bit Linux.
# July 2010:
#   Disable tests, support 10.5 and 32-bit Linux again.
#   Support 2.0 instead of 1.9.3.

import os, platform, shutil, subprocess, sys, time, pdb
from fnStartjsfunfuzz import *

path0 = os.path.dirname(sys.argv[0])
path2 = os.path.abspath(os.path.join(path0, "..", "js-autobisect"))
sys.path.append(path2)
import autoBisect

def main():

    # Variables
    selfTests = True
    multiTimedRunTimeout = '10'
    traceJit = True  # Activate support for tracing JIT in configure.
    jsJitSwitch = True  # Activate JIT fuzzing here.
    methodJit = False  # Method JIT is off by default unless fuzzing JM branch.
    # Pymake is activated on Windows platforms by default, for tip only.
    usePymake = True if os.name == 'nt' else False

    jsCompareJITSwitch = True
    # Disable compareJIT if traceJit support is disabled in configure.
    if not traceJit:
        jsCompareJITSwitch = False
    # Disable compareJIT for 1.9.1 and 1.9.2 branches.
    if sys.argv[3] == '191' or sys.argv[3] == '192':
        jsCompareJITSwitch = False

    # Activate to True to --enable-threadsafe for a multithreaded js shell.
    # Make sure NSPR is first installed! (Use `make` instead of `gmake`)
    #   https://developer.mozilla.org/en/NSPR_build_instructions
    threadsafe = False


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

    branchSupp = '['
    branchSupp += '|'.join('%s' % n for n in branchSuppList)
    branchSupp += ']'

    # There should be a minimum of 4 command-line parameters.
    if len(sys.argv) < 4:
        error(branchSupp)
        raise Exception('Too little command-line parameters.')

    # Check supported operating systems.
    macVer = osCheck()
    if (sys.argv[1] == '32') and (os.name == 'posix'):
        # For the Mac, 32-bit js shells have only been tested on i386.
        if (os.uname()[0] == 'Darwin' and os.uname()[4] != 'i386'):
            raise Exception('32-bit compilation is not supported on non-i386 Darwin platforms.')
    elif (sys.argv[1] == '64'):
        # 64-bit js shells have only been tested on Linux x86_64 (AMD64) platforms.
        if (os.uname()[0] == 'Linux' and os.uname()[4] != 'x86_64'):
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
                raise Exception('Valgrind on MacPorts for Snow Leopard isn\'t really ready..')
            else:
                exceptionBadOs()


    repoDict = {}
    # Definitions of the different repository and fuzzing locations.
    repoDict['fuzzing'] = '~/fuzzing/'
    repoDict['191'] = '~/mozilla-1.9.1/'
    repoDict['192'] = '~/mozilla-1.9.2/'
    repoDict['20'] = '~/mozilla-2.0/'
    #201support
    #repoDict['201'] = '~/mozilla-2.0.1/'
    repoDict['mc'] = '~/mozilla-central/'
    repoDict['tm'] = '~/tracemonkey/'
    repoDict['jm'] = '~/jaegermonkey/'
    fuzzPathStart = '~/Desktop/jsfunfuzz-'  # Start of fuzzing directory
    if os.name == 'nt' and 'Windows-XP' in platform.platform():
        for repo in repoDict.keys():
            # It is assumed that on WinXP, the corresponding directories are in the root folder.
            # e.g. Instead of `~/tracemonkey/`, TM would be in `/tracemonkey/`.
            repoDict[repo] = repoDict[repo][1:]
        fuzzPathStart = '/jsfunfuzz-'  # Start of fuzzing directory

    if verbose:
        for repo in repoDict.keys():
            verboseDump('The directory for the "' + repo + '" repository is "' + repoDict[repo] + '"')

    fuzzPath = fuzzPathStart + compileType + '-' + archNum + '-' + branchType + '/'
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
        (fuzzPath, onTip) = hgHashAddToFuzzPath(fuzzPath)
        os.chdir(os.path.expanduser(currDir))
    else:
        try:
            os.chdir(repoDict[branchType])
        except OSError:
            raise Exception('The directory for "' + branchType + '" is not found.')
        (fuzzPath, onTip) = hgHashAddToFuzzPath(fuzzPath)
        os.chdir(currDir)

    # Turn off pymake if not on tip.
    if usePymake and not onTip:
        usePymake = False

    # Create the fuzzing folder.
    try:
        # Rename directory if patches are applied, accept up to 2 patches.
        if len(sys.argv) >= 6 and (sys.argv[4] == 'patch' or sys.argv[6] == 'patch'):
            fuzzPath += 'patched/'
            verboseDump('Patched fuzzPath is: ' + fuzzPath)
        #os.makedirs(fuzzPath)
    except OSError:
        raise Exception('The fuzzing path at \'' + fuzzPath + '\' already exists!')


    # Copy the js tree to the fuzzPath.
    compilePath = os.path.join(fuzzPath, 'compilePath')
    cpJsTreeOrPymakeDir(repoDict[branchType], 'js', compilePath)
    # Copy the pymake build directory to the fuzzPath, if enabled.
    if usePymake:
        cpJsTreeOrPymakeDir(repoDict[branchType], 'build', compilePath)
    os.chdir(compilePath)  # Change into compilation directory.


    if jsCompareJITSwitch:
        # This patch makes the gc() function return an empty string (consistently)
        # rather than returning some information about the gc heap.
        verboseDump('Patching the gc() function now.')
        if 'Windows-XP' not in platform.platform():
            jsCompareJITCode = subprocess.call(['patch', '-p3', '-i', os.path.expanduser(repoDict['fuzzing']) + 'jsfunfuzz/patchGC.diff'])
        else:
            # We have to use `<` and `shell=True` here because of the drive letter of the path to patchGC.diff.
            # Python piping might be possible though slightly more complicated.
            jsCompareJITCode = subprocess.call(['patch -p3 < ' + repoDict['fuzzing'] + 'jsfunfuzz/patchGC.diff'], shell=True)
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

    autoconfRun(compilePath)

    # Create objdirs within the compilePaths.
    objdir = os.path.join(compilePath, compileType + '-objdir')
    os.mkdir(objdir)
    os.mkdir(os.path.join(compilePath, 'opt-objdir'))  # To compile the opt shell
    os.chdir(objdir)

    # Compile the first binary.
    cfgJsBin(archNum, compileType, traceJit, methodJit,
                      valgrindSupport, threadsafe, macVer, os.path.join(compilePath, 'configure'), objdir)
    if usePymake and os.name == 'nt':
        # This has to use `shell=True`.
        subprocess.call(['export SHELL'], shell=True)  # See https://developer.mozilla.org/en/pymake

    # Compile and copy the first binary.
    jsShellName = compileCopy(archNum, compileType, 'fooExtraID', usePymake, fuzzPath, objdir)
    # Change into compilePath for the second binary.
    os.chdir('../')

    # Test compilePath.
    verboseDump('This should be the compilePath:')
    verboseDump('%s\n' % os.getcwdu())
    if selfTests:
        if 'compilePath' not in os.getcwdu():
            raise Exception('We are not in compilePath.')

    # Compile the other binary.
    # No need to assign jsShellName here, because we are not fuzzing this one.
    if compileType == 'dbg':
        os.chdir('opt-objdir')
        cfgJsBin(archNum, compileType, traceJit, methodJit,
                          valgrindSupport, threadsafe, macVer, os.path.join(compilePath, 'configure'), objdir)
        compileCopy(archNum, 'opt', 'fooExtraID', usePymake, fuzzPath, objdir)
    elif compileType == 'opt':
        os.chdir('dbg-objdir')
        cfgJsBin(archNum, compileType, traceJit, methodJit,
                          valgrindSupport, threadsafe, macVer, os.path.join(compilePath, 'configure'), objdir)
        compileCopy(archNum, 'dbg', 'fooExtraID', usePymake, fuzzPath, objdir)


    os.chdir('../../')  # Change into fuzzPath directory.

    # Test fuzzPath.
    verboseDump('os.getcwdu() should be the fuzzPath:')
    verboseDump('%s/' % os.getcwdu())
    verboseDump('fuzzPath is: %s\n' % fuzzPath)
    if selfTests:
        if os.name == 'posix':
            if fuzzPath != (os.getcwdu() + '/'):
                raise Exception('We are not in fuzzPath.')
        elif os.name == 'nt':
            if fuzzPath[1:] != (os.getcwdu() + '/')[3:]:  # Ignore drive letter.
                raise Exception('We are not in fuzzPath.')

    # Copy over useful files that are updated in hg fuzzing branch.
    cpUsefulFiles(repoDict['fuzzing'] + 'jsfunfuzz/jsfunfuzz.js')
    cpUsefulFiles(repoDict['fuzzing'] + 'jsfunfuzz/analysis.py')
    cpUsefulFiles(repoDict['fuzzing'] + 'jsfunfuzz/findInterestingFiles.py')
    cpUsefulFiles(repoDict['fuzzing'] + 'jsfunfuzz/runFindInterestingFiles.sh')


    jsknownDict = {}
    # Define the corresponding js-known directories.
    jsknownDict['191'] = repoDict['fuzzing'] + 'js-known/mozilla-1.9.1/'
    jsknownDict['192'] = repoDict['fuzzing'] + 'js-known/mozilla-1.9.2/'
    jsknownDict['20'] = repoDict['fuzzing'] + 'js-known/mozilla-2.0/'
    #201support
    #jsknownDict['201'] = repoDict['fuzzing'] + 'js-known/mozilla-2.0.1/'
    jsknownDict['mc'] = repoDict['fuzzing'] + 'js-known/mozilla-central/'
    # For TM and JM, we use mozilla-central's js-known directories.
    jsknownDict['tm'] = repoDict['fuzzing'] + 'js-known/mozilla-central/'
    jsknownDict['jm'] = repoDict['fuzzing'] + 'js-known/mozilla-central/'

    multiTimedRun = repoDict['fuzzing'] + 'jsfunfuzz/multi_timed_run.py'

    if jsJitSwitch:
        jsJit = ' -j '
    else:
        jsJit = ' '
    if jsCompareJITSwitch:
        jsCompareJIT = ' --comparejit '
    else:
        jsCompareJIT = ' '
    if branchType == 'jm':
        jsMethodJit = ' -m '
    else:
        jsMethodJit = ' '


    # Commands to simulate bash's `tee`.
    tee = subprocess.Popen(['tee', 'log-jsfunfuzz'], stdin=subprocess.PIPE)


    # Define fuzzing command with the required parameters.
    if 'Windows-XP' not in platform.platform():
        multiTimedRun = os.path.expanduser(multiTimedRun)
        jsknownDict[branchType] = os.path.expanduser(jsknownDict[branchType])
    fuzzCmd1 = 'python -u ' + multiTimedRun + jsCompareJIT + multiTimedRunTimeout + ' '
    fuzzCmd2 = ' ' + fuzzPath + jsShellName + jsJit + jsMethodJit
    if valgrindSupport:
        fuzzCmd2 = ' valgrind' + fuzzCmd2
    fuzzCmd = fuzzCmd1 + jsknownDict[branchType] + fuzzCmd2

    verboseDump('jsShellName is: ' + jsShellName)
    verboseDump('fuzzPath + jsShellName is: ' + fuzzPath + jsShellName)
    verboseDump('fuzzCmd is: ' + fuzzCmd + '\n')


    # 32-bit or 64-bit verification test.
    if (os.name == 'posix'):
        if (os.uname()[0] == 'Linux') or (os.uname()[0] == 'Darwin'):
            test32or64bit(jsShellName, archNum)

    # Debug or optimized binary verification test.
    pdb.set_trace()
    testDbgOrOpt(jsShellName, compileType)


    print '''
    ================================================
    !  Fuzzing %s %s %s js shell builds now  !
       DATE: %s
    ================================================
    ''' % (archNum + '-bit', compileType, branchType, time.asctime( time.localtime(time.time()) ))

    # Commands to simulate bash's `tee`.
    # Start fuzzing the newly compiled builds.
    subprocess.call([fuzzCmd], stdout=tee.stdin, shell=True)


# Run main when run as a script, this line means it will not be run as a module.
if __name__ == '__main__':
    main()

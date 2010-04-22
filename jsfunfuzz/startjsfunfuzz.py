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

import sys, os, subprocess, shutil, time
from functionStartjsfunfuzz import *

def main():

    # Variables
    verbose = True  # Turning this on also enables tests.
    jsJitSwitch = True  # Activate JIT fuzzing here.
    # Pymake is activated on Windows platforms by default, for tip only.
    usePymake = True if os.name == 'nt' else False

    jsCompareJITSwitch = False
    # Disable compareJIT for 1.9.1 and 1.9.2 branches.
    if sys.argv[3] != '191' and sys.argv[3] != '192':
        jsCompareJITSwitch = True

    # Activate to True to --enable-threadsafe for a multithreaded js shell.
    # Make sure NSPR is first installed! (Use `make` instead of `gmake`)
    #   https://developer.mozilla.org/en/NSPR_build_instructions
    threadsafe = False
    multiTimedRunTimeout = '10'


    branchSuppList = []
    # Add supported branches here.
    branchSuppList.append('191')
    branchSuppList.append('192')
    #branchSuppList.append('193')  # Uncomment this for immediate 1.9.3 support
    #194support
    #branchSuppList.append('194')
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
    osCheck()
    if (sys.argv[1] == '32') and (os.name == 'posix'):
        if (os.uname()[0] == 'Linux'):
            raise Exception('32-bit compilation is not supported on Linux platforms.')
    elif (sys.argv[1] == '64'):
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
        if (os.uname()[0] == 'Linux' and
            (len(sys.argv) == 5 and sys.argv[4] == 'valgrind') or
            (len(sys.argv) == 7 and sys.argv[6] == 'valgrind') or
            (len(sys.argv) == 9 and sys.argv[8] == 'valgrind')):
            valgrindSupport = True
            # compareJIT is too slow..
            jsCompareJITSwitch = False  # Turn off compareJIT when in Valgrind.
            multiTimedRunTimeout = '300'  # Increase timeout to 300 in Valgrind.


    repoDict = {}
    # Definitions of the different repository and fuzzing locations.
    if os.name == 'posix':
        repoDict['fuzzing'] = '~/fuzzing/'
        repoDict['191'] = '~/mozilla-1.9.1/'
        repoDict['192'] = '~/mozilla-1.9.2/'
        repoDict['193'] = '~/mozilla-1.9.3/'
        #194support
        #repoDict['194'] = '~/mozilla-1.9.4/'
        repoDict['mc'] = '~/mozilla-central/'
        repoDict['tm'] = '~/tracemonkey/'
        repoDict['jm'] = '~/jaegermonkey/'
        fuzzPathStart = '~/Desktop/jsfunfuzz-'  # Start of fuzzing directory
    elif os.name == 'nt':
        repoDict['fuzzing'] = '/fuzzing/'
        repoDict['191'] = '/mozilla-1.9.1/'
        repoDict['192'] = '/mozilla-1.9.2/'
        repoDict['193'] = '/mozilla-1.9.3/'
        #194support
        #repoDict['194'] = '/mozilla-1.9.4/'
        repoDict['mc'] = '/mozilla-central/'
        repoDict['tm'] = '/tracemonkey/'
        repoDict['jm'] = '/jaegermonkey/'
        fuzzPathStart = '/jsfunfuzz-'  # Start of fuzzing directory

    if verbose:
        for repo in repoDict.keys():
            print 'DEBUG - The directory for the "' + repo + '" repository is "' + repoDict[repo] + '"'

    fuzzPath = fuzzPathStart + compileType + '-' + archNum + '-' + branchType + '/'
    if os.name == 'posix':
        fuzzPath = os.path.expanduser(fuzzPath)  # Expand the ~ folder on Linux/Mac.

    # Save the current directory as a variable.
    currDir = os.getcwd()

    # Note and attach the numbers and hashes of the current changeset in the fuzzPath.
    if os.name == 'posix':
        try:
            os.chdir(os.path.expanduser(repoDict[branchType]))
        except OSError:
            raise Exception('The directory for "' + branchType + '" is not found.')
        (fuzzPath, onTip) = hgHashAddToFuzzPath(fuzzPath)
        os.chdir(os.path.expanduser(currDir))
    elif os.name == 'nt':
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
            if verbose:
                print 'DEBUG - Patched fuzzPath is:', fuzzPath
        os.makedirs(fuzzPath)
    except OSError:
        raise Exception('The fuzzing path at \'' + fuzzPath + '\' already exists!')


    os.chdir(fuzzPath)  # Change to the fuzzing directory.
    # Copy the js tree to the fuzzPath.
    cpJsTreeOrPymakeDir(repoDict[branchType], 'js')
    # Copy the pymake build directory to the fuzzPath, if enabled.
    if usePymake:
        cpJsTreeOrPymakeDir(repoDict[branchType], 'build')
    os.chdir('compilePath')  # Change into compilation directory.


    if jsCompareJITSwitch:
        # This patch makes the gc() function return an empty string (consistently)
        # rather than returning some information about the gc heap.
        if verbose:
            print 'DEBUG - Patching the gc() function now.'
        jsCompareJITCode = subprocess.call(['patch -p3 < ' + repoDict['fuzzing'] + '/jsfunfuzz/patchGC.diff'], shell=True)
        if jsCompareJITCode == 1:
            raise Exception('Required js patch for --comparejit failed to patch.')

    # Patch the codebase if specified, accept up to 2 patches.
    patchReturnCode = 0
    patchReturnCode2 = 0
    if len(sys.argv) < 8 and len(sys.argv) >= 6 and sys.argv[4] == 'patch':
        patchReturnCode = subprocess.call(['patch -p3 < ' + sys.argv[5]], shell=True)
        if verbose:
            print 'DEBUG - Successfully incorporated the first patch.'
    elif len(sys.argv) >= 8 and sys.argv[6] == 'patch':
        patchReturnCode = subprocess.call(['patch -p3 < ' + sys.argv[5]], shell=True)
        if verbose:
            print 'DEBUG - Successfully incorporated the first patch.'
        patchReturnCode2 = subprocess.call(['patch -p3 < ' + sys.argv[7]], shell=True)
        if verbose:
            print 'DEBUG - Successfully incorporated the second patch.'
    if patchReturnCode == 1 or patchReturnCode2 == 1:
        raise Exception('Patching failed.')


    # Sniff platform and run different autoconf types:
    if os.name == 'posix':
        if os.uname()[0] == 'Darwin':
            subprocess.call(['autoconf213'])
        elif os.uname()[0] == 'Linux':
            subprocess.call(['autoconf2.13'])
    elif os.name == 'nt':
        subprocess.call(['sh', 'autoconf-2.13'])


    # Create objdirs within the compilePaths.
    os.mkdir('dbg-objdir')
    os.mkdir('opt-objdir')
    os.chdir(compileType + '-objdir')

    # Compile the first binary.
    configureJsBinary(archNum, compileType, branchType, valgrindSupport, threadsafe)
    if usePymake and os.name == 'nt':
        subprocess.call(['export SHELL'], shell=True)  # See https://developer.mozilla.org/en/pymake
    # Compile and copy the first binary.
    jsShellName = compileCopy(archNum, compileType, branchType, usePymake)
    # Change into compilePath for the second binary.
    os.chdir('../')

    # Test compilePath.
    if verbose:
        print 'DEBUG - This should be the compilePath:'
        print 'DEBUG - %s\n' % os.getcwdu()
        if 'compilePath' not in os.getcwdu():
            raise Exception('We are not in compilePath.')

    # Compile the other binary.
    # No need to assign jsShellName here, because we are not fuzzing this one.
    if compileType == 'dbg':
        os.chdir('opt-objdir')
        configureJsBinary(archNum, 'opt', branchType, valgrindSupport, threadsafe)
        compileCopy(archNum, 'opt', branchType, usePymake)
    elif compileType == 'opt':
        os.chdir('dbg-objdir')
        configureJsBinary(archNum, 'dbg', branchType, valgrindSupport, threadsafe)
        compileCopy(archNum, 'dbg', branchType, usePymake)


    os.chdir('../../')  # Change into fuzzPath directory.

    # Test fuzzPath.
    if verbose:
        print 'DEBUG - os.getcwdu() should be the fuzzPath:'
        print 'DEBUG - %s/' % os.getcwdu()
        print 'DEBUG - fuzzPath is: %s\n' % fuzzPath
        if os.name == 'posix':
            if fuzzPath != (os.getcwdu() + '/'):
                raise Exception('We are not in fuzzPath.')
        elif os.name == 'nt':
            if fuzzPath[1:] != (os.getcwdu() + '/')[3:]:  # Ignore drive letter.
                raise Exception('We are not in fuzzPath.')

    # Copy over useful files that are updated in hg fuzzing branch.
    jsfunfuzzFilePath = repoDict['fuzzing'] + 'jsfunfuzz/jsfunfuzz.js'
    analysisFilePath = repoDict['fuzzing'] + 'jsfunfuzz/analysis.py'
    findInterestingFilesFilePath = repoDict['fuzzing'] + 'jsfunfuzz/findInterestingFiles.py'
    if os.name == 'posix':
        jsfunfuzzFilePath = os.path.expanduser(jsfunfuzzFilePath)
        analysisFilePath = os.path.expanduser(analysisFilePath)
        findInterestingFilesFilePath = os.path.expanduser(findInterestingFilesFilePath)
    shutil.copy2(jsfunfuzzFilePath, '.')
    shutil.copy2(analysisFilePath, '.')
    shutil.copy2(findInterestingFilesFilePath, '.')


    jsknownDict = {}
    # Define the corresponding js-known directories.
    jsknownDict['191'] = repoDict['fuzzing'] + 'js-known/mozilla-1.9.1/'
    jsknownDict['192'] = repoDict['fuzzing'] + 'js-known/mozilla-1.9.2/'
    jsknownDict['193'] = repoDict['fuzzing'] + 'js-known/mozilla-1.9.3/'
    #194support
    #jsknownDict['194'] = repoDict['fuzzing'] + 'js-known/mozilla-1.9.4/'
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
    if os.name == 'posix':
        multiTimedRun = os.path.expanduser(multiTimedRun)
    fuzzCmd1 = 'python -u ' + multiTimedRun + jsCompareJIT + multiTimedRunTimeout + ' '
    fuzzCmd2 = ' ' + fuzzPath + jsShellName + jsJit + jsMethodJit
    if valgrindSupport:
        fuzzCmd2 = ' valgrind' + fuzzCmd2
    fuzzCmd = fuzzCmd1 + jsknownDict[branchType] + fuzzCmd2

    if verbose:
        print 'DEBUG - jsShellName is: ' + jsShellName
        print 'DEBUG - fuzzPath + jsShellName is: ' + fuzzPath + jsShellName
        print 'DEBUG - fuzzCmd is: ' + fuzzCmd
        print


    # 32-bit or 64-bit verification test.
    if (os.name == 'posix'):
        if os.uname()[0] == 'Darwin':
            test32or64bit(jsShellName, archNum)

    # Debug or optimized binary verification test.
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

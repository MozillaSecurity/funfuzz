#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import platform
import sys

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
from subprocesses import envWithPath, captureStdout, isMac, isWin, isMozBuild64, normExpUserPath, \
    shellify, vdump

if os.name == 'nt':
    COMPILE_NSPR_LIB = 'libnspr4.lib' if isMozBuild64 else 'nspr4.lib'
    COMPILE_PLDS_LIB = 'libplds4.lib' if isMozBuild64 else 'plds4.lib'
    COMPILE_PLC_LIB = 'libplc4.lib' if isMozBuild64 else 'plc4.lib'

    RUN_NSPR_LIB = 'libnspr4.dll' if isMozBuild64 else 'nspr4.dll'
    RUN_PLDS_LIB = 'libplds4.dll' if isMozBuild64 else 'plds4.dll'
    RUN_PLC_LIB = 'libplc4.dll' if isMozBuild64 else 'plc4.dll'
else:
    COMPILE_NSPR_LIB = 'libnspr4.a'
    COMPILE_PLDS_LIB = 'libplds4.a'
    COMPILE_PLC_LIB = 'libplc4.a'

    if platform.system() == 'Darwin':
        RUN_NSPR_LIB = 'libnspr4.dylib'
        RUN_PLDS_LIB = 'libplds4.dylib'
        RUN_PLC_LIB = 'libplc4.dylib'
    elif (platform.system() == 'Linux'):
        RUN_NSPR_LIB = 'libnspr4.so'
        RUN_PLDS_LIB = 'libplds4.so'
        RUN_PLC_LIB = 'libplc4.so'

ALL_COMPILE_LIBS = (COMPILE_NSPR_LIB, COMPILE_PLDS_LIB, COMPILE_PLC_LIB)
ALL_RUN_LIBS = (RUN_NSPR_LIB, RUN_PLDS_LIB, RUN_PLC_LIB)

def archOfBinary(binary):
    '''This function tests if a binary is 32-bit or 64-bit.'''
    unsplitFiletype = captureStdout(['file', binary])[0]
    filetype = unsplitFiletype.split(':', 1)[1]
    if isWin:
        assert 'PE executable for MS Windows (console)' in filetype
        return '32' if 'Intel 80386 32-bit' in filetype else '64'
    else:
        if 'universal binary' in filetype:
            raise Exception("I don't know how to deal with multiple-architecture binaries")
        if '32-bit' in filetype or 'i386' in filetype:
            assert '64-bit' not in filetype
            return '32'
        if '64-bit' in filetype:
            assert '32-bit' not in filetype
            return '64'

def constructVgCmdList(errorCode=77):
    '''Constructs default parameters needed to run valgrind with.'''
    vgCmdList = []
    vgCmdList.append('valgrind')
    if isMac:
        vgCmdList.append('--dsymutil=yes')
    vgCmdList.append('--error-exitcode=' + str(errorCode))
    vgCmdList.append('--smc-check=all-non-file')
    # See bug 913876 comment 18:
    vgCmdList.append('--vex-iropt-register-updates=allregs-at-mem-access')
    vgCmdList.append('--partial-loads-ok=yes')  # See bug 913883 comment 3
    vgCmdList.append('--gen-suppressions=all')
    vgCmdList.append('--leak-check=full')
    vgCmdList.append('--show-possibly-lost=no')
    vgCmdList.append('--num-callers=50')
    return vgCmdList

def shellSupports(shellPath, args):
    '''
    This function returns True if the shell likes the args.
    You can support for a function, e.g. ['-e', 'foo()'], or a flag, e.g. ['-j', '-e', '42'].
    '''
    output, retCode = testBinary(shellPath, args, False, False)
    if retCode == 0:
        return True
    elif 1 <= retCode <= 3:
        # Exit codes 1 through 3 are all plausible "non-support":
        #   * "Usage error" is 1 in new js shell, 2 in old js shell, 2 in xpcshell.
        #   * "Script threw an error" is 3 in most shells, but 1 in some versions (see bug 751425).
        # Since we want autoBisect to support all shell versions, allow all these exit codes.
        return False
    else:
        raise Exception('Unexpected exit code in shellSupports ' + str(retCode))

def testBinary(shellPath, args, useValgrind, threadsafeShell):
    '''Tests the given shell with the given args.'''
    testCmd = (constructVgCmdList() if useValgrind else []) + [shellPath] + args
    vdump('The testing command is: ' + shellify(testCmd))

    newEnv = envWithPath(os.path.dirname(os.path.abspath(shellPath)))
    if threadsafeShell:
        # The NSPR libraries needed to run threadsafe js shell should have already been be copied to
        # the same destination as the shell.
        assert os.path.isfile(normExpUserPath(os.path.join(
            os.path.dirname(os.path.abspath(shellPath)), RUN_NSPR_LIB)))
        assert os.path.isfile(normExpUserPath(os.path.join(
            os.path.dirname(os.path.abspath(shellPath)), RUN_PLDS_LIB)))
        assert os.path.isfile(normExpUserPath(os.path.join(
            os.path.dirname(os.path.abspath(shellPath)), RUN_PLC_LIB)))
    out, rCode = captureStdout(testCmd, combineStderr=True, ignoreStderr=True, ignoreExitCode=True,
                               env=newEnv)
    vdump('The exit code is: ' + str(rCode))
    return out, rCode

def testDbgOrOpt(s):
    '''This function tests if a binary is a debug or optimized shell.'''
    # Do not use disassemble(), old shells prior to cc4fdccc1135 did not have disassemble(), and
    # it landed fairly recently on March 31, 2011. See bug 396512 comment 36.
    # The changeset's patch date is not reflective of its actual landing date.
    return 'dbg' if shellSupports(s, ['-e', 'dis()']) else 'opt'

def testGetBuildConfiguration(s):
    '''This function tests if a binary supports getBuildConfiguration().'''
    return shellSupports(s, ['-e', 'getBuildConfiguration()'])

def testGetBuildConfigurationWithThreadsafe(s):
    '''
    This function tests if a binary supports getBuildConfiguration() with threadsafe.
    See bug 791146 - getBuildConfiguration() returns the wrong value for gczeal and threadsafe
    '''
    ans = testBinary(s,
            ['-e', 'print(getBuildConfiguration().hasOwnProperty("threadsafe"))'], False, False)[0]
    return ans.find('true') != -1

def testJsShellOrXpcshell(s):
    '''This function tests if a binary is a js shell or xpcshell.'''
    return 'xpcshell' if shellSupports(s, ['-e', 'Components']) else 'jsShell'

def queryBuildConfiguration(s, parameter):
    '''Tests if a binary is compiled with specified parameters, in getBuildConfiguration().'''
    ans = testBinary(s, ['-e', 'print(getBuildConfiguration()["' + parameter + '"])'],
                     False, False)[0]
    return ans.find('true') != -1


def testIsHardFpShellARM(s):
    '''Tests if the ARM shell is compiled with hardfp support.'''
    readelfBin = '/usr/bin/readelf'
    if os.path.exists(readelfBin):
        newEnv = envWithPath(os.path.dirname(os.path.abspath(s)))
        readelfOutput = captureStdout([readelfBin, '-A', s], env=newEnv)[0]
        return ('Tag_ABI_VFP_args: VFP registers' in readelfOutput)
    else:
        raise Exception('readelf is not found.')


def verifyBinary(sh, options):
    '''Verifies that the binary is compiled as intended.'''
    assert archOfBinary(sh.getShellBaseTempDirWithName()) == sh.buildOptions.arch
    assert testDbgOrOpt(sh.getShellBaseTempDirWithName()) == sh.buildOptions.compileType
    if platform.uname()[4] == 'armv7l':
        assert testIsHardFpShellARM(sh.getShellBaseTempDirWithName()) == options.enableHardFp
    if testGetBuildConfiguration(sh.getShellBaseTempDirWithName()):
        if testGetBuildConfigurationWithThreadsafe(sh.getShellBaseTempDirWithName()):
            assert queryBuildConfiguration(sh.getShellBaseTempDirWithName(), 'threadsafe') == \
                options.isThreadsafe
        assert queryBuildConfiguration(sh.getShellBaseTempDirWithName(), 'more-deterministic') == \
            options.enableMoreDeterministic
        assert queryBuildConfiguration(sh.getShellBaseTempDirWithName(), 'asan') == \
            options.buildWithAsan
        assert queryBuildConfiguration(sh.getShellBaseTempDirWithName(), 'rooting-analysis') == \
            options.enableRootAnalysis
        assert queryBuildConfiguration(sh.getShellBaseTempDirWithName(), 'exact-rooting') == \
            options.enableExactRooting
        assert queryBuildConfiguration(sh.getShellBaseTempDirWithName(), 'generational-gc') == \
            options.enableGcGenerational

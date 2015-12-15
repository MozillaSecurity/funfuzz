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
import subprocesses as sps

path2 = os.path.abspath(os.path.join(path0, os.pardir, os.pardir, 'lithium', 'interestingness'))
sys.path.append(path2)
if not os.path.exists(path2):
    print "Please check out Lithium and FuzzManager side-by-side with funfuzz. Links in https://github.com/MozillaSecurity/funfuzz/#setup"
    sys.exit(2)
import envVars


if sps.isWin:
    # Update if the following changes:
    # https://dxr.mozilla.org/mozilla-central/search?q=%3C%2FOutputFile%3E+.dll+path%3Aintl%2Ficu%2Fsource%2F&case=true
    RUN_ICUUC_LIB_EXCL_EXT = 'icuuc'
    # Debug builds seem to have their debug "d" notation *before* the ICU version.
    # Check https://dxr.mozilla.org/mozilla-central/search?q=%40BINPATH%40%2Ficudt&case=true&redirect=true
    RUN_ICUUCD_LIB_EXCL_EXT = 'icuucd'
    RUN_ICUIN_LIB_EXCL_EXT = 'icuin'
    RUN_ICUIND_LIB_EXCL_EXT = 'icuind'
    RUN_ICUIO_LIB_EXCL_EXT = 'icuio'
    RUN_ICUIOD_LIB_EXCL_EXT = 'icuiod'
    RUN_ICUDT_LIB_EXCL_EXT = 'icudt'
    RUN_ICUDTD_LIB_EXCL_EXT = 'icudtd'
    RUN_ICUTEST_LIB_EXCL_EXT = 'icutest'
    RUN_ICUTESTD_LIB_EXCL_EXT = 'icutestd'
    RUN_ICUTU_LIB_EXCL_EXT = 'icutu'
    RUN_ICUTUD_LIB_EXCL_EXT = 'icutud'

    RUN_MOZGLUE_LIB = 'mozglue.dll'
    RUN_TESTPLUG_LIB = 'testplug.dll'
elif platform.system() == 'Darwin':
    RUN_MOZGLUE_LIB = 'libmozglue.dylib'
elif platform.system() == 'Linux':
    RUN_MOZGLUE_LIB = 'libmozglue.so'

# These include running the js shell (mozglue) and should be in dist/bin.
# At least Windows required the ICU libraries.
ALL_RUN_LIBS = [RUN_MOZGLUE_LIB]
if sps.isWin:
    ALL_RUN_LIBS.append(RUN_TESTPLUG_LIB)
    for icu_ver in (52, 55, 56):
        ALL_RUN_LIBS.append(RUN_ICUUC_LIB_EXCL_EXT + str(icu_ver) + '.dll')
        ALL_RUN_LIBS.append(RUN_ICUUCD_LIB_EXCL_EXT + str(icu_ver) + '.dll')
        ALL_RUN_LIBS.append(RUN_ICUIN_LIB_EXCL_EXT + str(icu_ver) + '.dll')
        ALL_RUN_LIBS.append(RUN_ICUIND_LIB_EXCL_EXT + str(icu_ver) + '.dll')
        ALL_RUN_LIBS.append(RUN_ICUIO_LIB_EXCL_EXT + str(icu_ver) + '.dll')
        ALL_RUN_LIBS.append(RUN_ICUIOD_LIB_EXCL_EXT + str(icu_ver) + '.dll')
        ALL_RUN_LIBS.append(RUN_ICUDT_LIB_EXCL_EXT + str(icu_ver) + '.dll')
        ALL_RUN_LIBS.append(RUN_ICUDTD_LIB_EXCL_EXT + str(icu_ver) + '.dll')
        ALL_RUN_LIBS.append(RUN_ICUTEST_LIB_EXCL_EXT + str(icu_ver) + '.dll')
        ALL_RUN_LIBS.append(RUN_ICUTESTD_LIB_EXCL_EXT + str(icu_ver) + '.dll')
        ALL_RUN_LIBS.append(RUN_ICUTU_LIB_EXCL_EXT + str(icu_ver) + '.dll')
        ALL_RUN_LIBS.append(RUN_ICUTUD_LIB_EXCL_EXT + str(icu_ver) + '.dll')


def archOfBinary(binary):
    '''This function tests if a binary is 32-bit or 64-bit.'''
    unsplitFiletype = sps.captureStdout(['file', binary])[0]
    filetype = unsplitFiletype.split(':', 1)[1]
    if sps.isWin:
        assert 'MS Windows' in filetype
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
    if sps.isMac:
        vgCmdList.append('--dsymutil=yes')
    vgCmdList.append('--error-exitcode=' + str(errorCode))
    if not sps.isARMv7l:  # jseward mentioned that ARM does not need --smc-check=<something>
        vgCmdList.append('--smc-check=all-non-file')
    # See bug 913876 comment 18:
    vgCmdList.append('--vex-iropt-register-updates=allregs-at-mem-access')
    vgCmdList.append('--gen-suppressions=all')
    vgCmdList.append('--leak-check=full')
    vgCmdList.append('--errors-for-leak-kinds=definite')
    vgCmdList.append('--show-leak-kinds=definite')
    vgCmdList.append('--show-possibly-lost=no')
    vgCmdList.append('--num-callers=50')
    return vgCmdList


def shellSupports(shellPath, args):
    '''
    This function returns True if the shell likes the args.
    You can support for a function, e.g. ['-e', 'foo()'], or a flag, e.g. ['-j', '-e', '42'].
    '''
    retCode = testBinary(shellPath, args, False)[1]
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


def testBinary(shellPath, args, useValgrind):
    '''Tests the given shell with the given args.'''
    testCmd = (constructVgCmdList() if useValgrind else []) + [shellPath] + args
    sps.vdump('The testing command is: ' + sps.shellify(testCmd))
    out, rCode = sps.captureStdout(testCmd, combineStderr=True, ignoreStderr=True,
                                   ignoreExitCode=True, env=envVars.envWithPath(
                                       os.path.dirname(os.path.abspath(shellPath))))
    sps.vdump('The exit code is: ' + str(rCode))
    return out, rCode


def testJsShellOrXpcshell(s):
    '''This function tests if a binary is a js shell or xpcshell.'''
    return 'xpcshell' if shellSupports(s, ['-e', 'Components']) else 'jsShell'


def queryBuildConfiguration(s, parameter):
    '''Tests if a binary is compiled with specified parameters, in getBuildConfiguration().'''
    ans = testBinary(s, ['-e', 'print(getBuildConfiguration()["' + parameter + '"])'],
                     False)[0]
    return ans.find('true') != -1


def testIsHardFpShellARM(s):
    '''Tests if the ARM shell is compiled with hardfp support.'''
    readelfBin = '/usr/bin/readelf'
    if os.path.exists(readelfBin):
        newEnv = envVars.envWithPath(os.path.dirname(os.path.abspath(s)))
        readelfOutput = sps.captureStdout([readelfBin, '-A', s], env=newEnv)[0]
        return 'Tag_ABI_VFP_args: VFP registers' in readelfOutput
    else:
        raise Exception('readelf is not found.')


def verifyBinary(sh):
    '''Verifies that the binary is compiled as intended.'''
    binary = sh.getShellCacheFullPath()

    assert archOfBinary(binary) == ('32' if sh.buildOptions.enable32 else '64')

    # Testing for debug or opt builds are different because there can be hybrid debug-opt builds.
    assert queryBuildConfiguration(binary, 'debug') == sh.buildOptions.enableDbg

    if sps.isARMv7l:
        assert testIsHardFpShellARM(binary) == sh.buildOptions.enableHardFp

    assert queryBuildConfiguration(binary, 'more-deterministic') == sh.buildOptions.enableMoreDeterministic
    assert queryBuildConfiguration(binary, 'asan') == sh.buildOptions.buildWithAsan
    assert (queryBuildConfiguration(binary, 'arm-simulator') and sh.buildOptions.enable32) == sh.buildOptions.enableSimulatorArm32
    assert (queryBuildConfiguration(binary, 'arm-simulator') and not sh.buildOptions.enable32) == sh.buildOptions.enableSimulatorArm64

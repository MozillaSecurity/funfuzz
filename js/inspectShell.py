#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import with_statement

import os
import platform
import subprocess
import sys
from copy import deepcopy

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
from subprocesses import captureStdout, isLinux, isMac, isWin, shellify, vdump

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
        if '386' in filetype or '32-bit' in filetype:
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
    output, retCode = testBinary(shellPath, args, False)
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
    vdump('The testing command is: ' + shellify(testCmd))

    cfgEnvDt = deepcopy(os.environ)
    if isLinux:
        cfgEnvDt['LD_LIBRARY_PATH'] = os.path.dirname(os.path.abspath(shellPath))
    out, rCode = captureStdout(testCmd, combineStderr=True, ignoreStderr=True, ignoreExitCode=True,
                               env=cfgEnvDt)
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
    return captureStdout([s, '-e',
        'print(getBuildConfiguration().hasOwnProperty("threadsafe"))'])[0].find('true') != -1

def testJsShellOrXpcshell(s):
    '''This function tests if a binary is a js shell or xpcshell.'''
    return 'xpcshell' if shellSupports(s, ['-e', 'Components']) else 'jsShell'

def queryBuildConfiguration(s, parameter):
    '''Tests if a binary is compiled with specified parameters, in getBuildConfiguration().'''
    return captureStdout([s, '-e',
        'print(getBuildConfiguration()["' + parameter + '"])'])[0].find('true') != -1

def verifyBinary(sh, options):
    '''Verifies that the binary is compiled as intended.'''
    assert archOfBinary(sh.getShellBaseTempDir()) == sh.getArch()
    assert testDbgOrOpt(sh.getShellBaseTempDir()) == sh.getCompileType()
    if testGetBuildConfiguration(sh.getShellBaseTempDir()):
        if testGetBuildConfigurationWithThreadsafe(sh.getShellBaseTempDir()):
            assert queryBuildConfiguration(sh.getShellBaseTempDir(), 'threadsafe') == \
                options.isThreadsafe
        assert queryBuildConfiguration(sh.getShellBaseTempDir(), 'rooting-analysis') == \
            options.enableRootAnalysis

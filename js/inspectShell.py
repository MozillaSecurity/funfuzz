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
from subprocesses import captureStdout, isWin, isLinux, vdump

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

def shellSupports(shell, args):
    '''
    This function returns True if the shell likes the args.
    You can support for a function, e.g. ['-e', 'foo()'], or a flag, e.g. ['-j', '-e', '42'].
    '''
    cmdList = [shell] + args

    vdump(' '.join(cmdList))
    cfgEnvDt = deepcopy(os.environ)
    if isLinux:
        cfgEnvDt['LD_LIBRARY_PATH'] = os.path.dirname(os.path.abspath(shell))
    out, retCode = captureStdout(cmdList, ignoreStderr=True, combineStderr=True,
                                 ignoreExitCode=True, env=cfgEnvDt)
    vdump('The return code is: ' + str(retCode))

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

def testJsShellOrXpcshell(s):
    '''This function tests if a binary is a js shell or xpcshell.'''
    return 'xpcshell' if shellSupports(s, ['-e', 'Components']) else 'jsShell'

def testDbgOrOpt(s):
    '''This function tests if a binary is a debug or optimized shell.'''
    return 'dbg' if shellSupports(s, ['-e', 'disassemble()']) else 'opt'

def testIsThreadsafe(s):
    '''This function tests if a binary is compiled with --enable-threadsafe.'''
    result = captureStdout([s, '-e', 'print(getBuildConfiguration()["threadsafe"])'])[0]
    # There were some changesets which had getBuildConfiguration() but with no threadsafe attribute
    if result not in locals():
        result = 'undef'
    return result

def testWithRootAnalysis(s):
    '''This function tests if a binary is compiled with root analysis enabled.'''
    return bool(captureStdout([s, '-e', 'print(getBuildConfiguration()["rooting-analysis"])'])[0])

def verifyBinary(sh, options):
    '''Verifies that the binary is compiled as intended.'''
    assert archOfBinary(sh.getShellFuzzingPath()) == sh.getArch()
    assert testDbgOrOpt(sh.getShellFuzzingPath()) == sh.getCompileType()
    assert testIsThreadsafe(sh.getShellFuzzingPath()) == \
        ('undef' or (True if options.isThreadsafe else False))
    assert testWithRootAnalysis(sh.getShellFuzzingPath()) == (True if options.raSupport else False)

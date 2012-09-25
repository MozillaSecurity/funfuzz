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

from shellFlags import shellSupports

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
    # and there were older changesets which did not have getBuildConfiguration() at all.
    if result not in locals():
        result = 'undef'
    return result

def testWithRootAnalysis(s):
    '''This function tests if a binary is compiled with root analysis enabled.'''
    result = captureStdout([s, '-e', 'print(getBuildConfiguration()["rooting-analysis"])'])[0]
    # There were some changesets which did not have getBuildConfiguration() at all.
    if result not in locals():
        result = 'undef'
    return result

def verifyBinary(sh, options):
    '''Verifies that the binary is compiled as intended.'''
    assert archOfBinary(sh.getShellFuzzingPath()) == sh.getArch()
    assert testDbgOrOpt(sh.getShellFuzzingPath()) == sh.getCompileType()
    assert testIsThreadsafe(sh.getShellFuzzingPath()) == ('undef' or options.isThreadsafe)
    assert testWithRootAnalysis(sh.getShellFuzzingPath()) == ('undef' or options.enableRootAnalysis)

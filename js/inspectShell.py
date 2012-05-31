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

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
from subprocesses import captureStdout, verbose, vdump

def archOfBinary(b):
    '''
    This function tests if a binary is 32-bit or 64-bit.
    '''
    unsplitFiletype = captureStdout(['file', b])[0]
    filetype = unsplitFiletype.split(':', 1)[1]
    if platform.system() == 'Windows':
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
    if verbose:
        retCode = subprocess.call(cmdList, stderr=subprocess.STDOUT)
    else:
        fnull = open(os.devnull, 'w')
        retCode = subprocess.call(cmdList, stdout=fnull, stderr=subprocess.STDOUT)
        fnull.close()

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

def testJsShellOrXpcshell(sname):
    '''
    This function tests if a binary is a js shell or xpcshell.
    '''
    if shellSupports(sname, ['-e', 'Components']):
        return 'xpcshell'
    else:
        return 'jsShell'

def testDbgOrOpt(jsShellName):
    '''
    This function tests if a binary is a debug or optimized shell.
    '''
    if shellSupports(jsShellName, ['-e', 'gczeal(0)']):
        return 'dbg'
    else:
        return 'opt'

if __name__ == '__main__':
    pass

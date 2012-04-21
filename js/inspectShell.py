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

from tempfile import NamedTemporaryFile
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

def exitCodeDbgOptOrJsShellXpcshell(shell, dbgOptOrJsShellXpcshell, cwd=os.getcwdu()):
    '''
    This function returns the exit code after testing the shell.
    '''
    contents = ''
    contentsList = []
    cmdList = []
    # The following line (specifically the delete keyword) is incompatible with Python 2.5
    f = NamedTemporaryFile(delete=False)  # Don't delete upon close; Windows needs it to be closed.

    cmdList.append(shell)
    if dbgOptOrJsShellXpcshell == 'dbgOpt':
        contents = 'gczeal()'
    elif dbgOptOrJsShellXpcshell == 'jsShellXpcshell':
        contents = 'Components'
        # To run xpcshell, command is `./run-mozilla.sh ./xpcshell testcase.js`
        # js shells do not have the middle parameter, so they will mis-understand and think that
        # ./xpcshell is the testcase they should run instead.
        if 'run-mozilla' in shell:
            cmdList.append('./xpcshell')
            assert len(cmdList) == 2
        else:
            assert len(cmdList) == 1

    contentsList.append(contents)
    f.writelines(contentsList)
    f.flush()  # Important! Or else nothing will be in the file when the js shell executes the file.
    f.close()  # We have to close the file here, or else Windows won't be able to access the file.

    cmdList.append(f.name)
    vdump(' '.join(cmdList))
    if verbose:
        retCode = subprocess.call(cmdList, stderr=subprocess.STDOUT, cwd=cwd)
    else:
        fnull = open(os.devnull, 'w')
        retCode = subprocess.call(cmdList, stdout=fnull, stderr=subprocess.STDOUT, cwd=cwd)
        fnull.close()

    # Verbose logging.
    vdump('The contents of ' + f.name + ' is:')
    if verbose:
        with open(f.name, 'rb') as f:
            print ''.join([line for line in f.readlines() if verbose])

    assert os.path.exists(f.name)
    os.remove(f.name)
    assert not os.path.exists(f.name)
    vdump('The return code is: ' + str(retCode))
    return retCode

def testJsShellOrXpcshell(sname, cwd=os.getcwdu()):
    '''
    This function tests if a binary is a js shell or xpcshell.
    '''
    exitCode = exitCodeDbgOptOrJsShellXpcshell(sname, 'jsShellXpcshell', cwd=cwd)

    # The error code for xpcshells when passing in the Components function should be 0.
    if exitCode == 0:
        return 'xpcshell'
    # js shells don't have Components compiled in by default.
    elif exitCode == 3:
        return 'jsShell'
    else:
        raise Exception('Unknown exit code after testing if js shell or xpcshell: ' + str(exitCode))

def testDbgOrOpt(jsShellName, cwd=os.getcwdu()):
    '''
    This function tests if a binary is a debug or optimized shell.
    '''
    exitCode = exitCodeDbgOptOrJsShellXpcshell(jsShellName, 'dbgOpt', cwd=cwd)

    # The error code for debug shells when passing in the gczeal() function should be 0.
    if exitCode == 0:
        return 'dbg'
    # Optimized shells don't have gczeal() compiled in by default.
    elif exitCode == 3:
        return 'opt'
    else:
        raise Exception('Unknown exit code after testing if debug or opt: ' + exitCode)

def testDbgOrOptGivenACompileType(jsShellName, compileType, cwd=os.getcwdu()):
    '''
    This function tests if a binary is a debug or optimized shell given a compileType.
    '''
    exitCode = exitCodeDbgOptOrJsShellXpcshell(jsShellName, 'dbgOpt', cwd=cwd)

    vdump('The error code for debug shells should be 0.')
    vdump('The error code for opt shells should be 3.')
    vdump('The actual error code for ' + jsShellName + ' now, is: ' + str(exitCode))

    # The error code for debug shells when passing in the gczeal() function should be 0.
    if compileType == 'dbg' and exitCode != 0:
        print 'ERROR: A debug shell tested with gczeal() should return "0" as the error code.'
        print 'compileType is: ' + compileType
        print 'exitCode is: ' + str(exitCode)
        print
        raise Exception('The compiled binary is not a debug shell.')
    # Optimized shells don't have gczeal() compiled in by default.
    elif compileType == 'opt' and exitCode != 3:
        print 'ERROR: An optimized shell tested with gczeal() should return "3" as the error code.'
        print 'compileType is: ' + compileType
        print 'exitCode is: ' + str(exitCode)
        print
        raise Exception('The compiled binary is not an optimized shell.')

if __name__ == '__main__':
    pass

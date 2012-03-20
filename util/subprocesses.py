#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import pdb
import platform
import subprocess
import time

verbose = False

########################
#  Platform Detection  #
########################

def macType():
    '''
    If system is a Mac, return the mac type.
    '''
    assert platform.system() in ('Windows', 'Linux', 'Darwin')
    isMac = isSL = amiLion = False
    if platform.system() == 'Darwin':
        isMac = True
        # Script has only been tested on Snow Leopard and Lion.
        assert 6 <= int(platform.mac_ver()[0].split('.')[1]) <= 7
        isSL = isMac and platform.mac_ver()[0].split('.')[1] == '6' \
            and platform.mac_ver()[0].split('.') >= ['10', '6']
        amiLion = isMac and platform.mac_ver()[0].split('.')[1] == '7' \
            and platform.mac_ver()[0].split('.') >= ['10', '7']
    return (isMac, isSL, amiLion)

def isVM():
    '''
    Returns the OS of the system, if system is a VM.
    '''
    vm = False
    # In VMware, shared folders are in z:, and we copy from the shared folders to avoid having
    # another copy of the repository in the VM.
    if (platform.uname()[2] == 'XP' \
            and os.path.exists(os.path.join('z:', os.sep, 'fuzzing'))) or \
        platform.uname()[0] == 'Linux' \
            and os.path.exists(os.path.join('/', 'mnt', 'hgfs', 'fuzzing')):
        assert not os.path.exists(normExpUserPath(os.path.join('~', 'fuzzing')))
        assert not os.path.exists(normExpUserPath(os.path.join('~', 'trees')))
        vm = True
    return (platform.system(), vm)

#####################
#  Shell Functions  #
#####################

def captureStdout(cmd, ignoreStderr=False, combineStderr=False, ignoreExitCode=False,
                  currWorkingDir=os.getcwdu(), env=os.environ, verbosity=False):
    '''
    Captures standard output, returns the output as a string, along with the return value.
    '''
    vdump(' '.join(cmd))
    p = subprocess.Popen(cmd,
        stdin = subprocess.PIPE,
        stdout = subprocess.PIPE,
        stderr = subprocess.STDOUT if combineStderr else subprocess.PIPE,
        cwd=currWorkingDir, env=env)
    (stdout, stderr) = p.communicate()
    if not ignoreExitCode and p.returncode != 0:
        # Potential problem area: Note that having a non-zero exit code does not mean that the
        # operation did not succeed, for example when compiling a shell. A non-zero exit code can
        # appear even though a shell compiled successfully. This issue has been bypassed in the
        # makeShell function in autoBisect.
        # Pymake in builds earlier than revision 232553f741a0 did not support the '-s' option.
        if 'no such option: -s' not in stdout:
            print 'Nonzero exit code from ' + repr(cmd)
            print stdout
        if stderr is not None:
            print stderr
        # Pymake in builds earlier than revision 232553f741a0 did not support the '-s' option.
        if 'hg pull: option --rebase not recognized' not in stdout and \
          'no such option: -s' not in stdout:
            raise Exception('Nonzero exit code')
    if not combineStderr and not ignoreStderr and len(stderr) > 0:
        if not ((platform.system() == 'Windows' and \
            # Ignore hg color mode throwing an error in console on Windows platforms.
            'warning: failed to set color mode to win32' in stderr) or \
            (isVM() == ('Linux', True) and \
            # Ignore stderr warning when running a Linux VM on a Mac host:
            # Not trusting file /mnt/hgfs/trees/mozilla-central/.hg/hgrc from untrusted user 501...
            'hgrc from untrusted user 501' in stderr)):
            print 'Unexpected output on stderr from ' + repr(cmd)
            print stdout, stderr
            raise Exception('Unexpected output on stderr')
    if stderr and ignoreStderr and len(stderr) > 0 and p.returncode != 0:
        # During configure, there will always be stderr. Sometimes this stderr causes configure to
        # stop the entire script, especially on Windows.
        print 'Return code not zero, and unexpected output on stderr from ' + repr(cmd)
        print stdout, stderr
        raise Exception('Return code not zero, and unexpected output on stderr')
    if verbose or verbosity:
        print stdout
        if stderr is not None:
            print stderr
    return stdout.rstrip(), p.returncode

def dateStr():
    '''
    Equivalent of: assert subprocess.check_output(['Date'])[:-1] == currDateTime
    '''
    currTz = time.tzname[0] if time.daylight == 1 else time.tzname[1]
    currAscDateTime = time.asctime( time.localtime(time.time()) )
    currDateTime = currAscDateTime[:-4] + currTz + ' ' + currAscDateTime[-4:]
    return currDateTime

def normExpUserPath(p):
    return os.path.normpath(os.path.expanduser(p))

def timeSubprocess(command, cwd=os.getcwdu(), vb=False):
    '''
    Calculates how long a captureStdout command takes and prints it. Returns the stdout and return
    value that captureStdout passes on.
    '''
    print 'Running `%s` now..' % ' '.join(command)
    startTime = time.time()
    stdOutput, retVal = captureStdout(
        command, ignoreStderr=True, combineStderr=True, currWorkingDir=cwd, verbosity=vb)
    endTime = time.time()
    print '`' + ' '.join(command) + '` took %.3f seconds.\n' % (endTime - startTime)
    return stdOutput, retVal

def vdump(inp):
    '''
    This function appends the word 'DEBUG' to any verbose output.
    '''
    if verbose:
        print 'DEBUG -', inp

if __name__ == '__main__':
    pass

#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import ctypes
import errno
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import time

verbose = False

isARMv7l = (platform.uname()[4] == 'armv7l')
isLinux = (platform.system() == 'Linux')
isMac = (platform.system() == 'Darwin')
isWin = (platform.system() == 'Windows')
isWin64 = ('PROGRAMFILES(X86)' in os.environ)
isWinVistaOrHigher = isWin and (sys.getwindowsversion()[0] >= 6)
# This refers to the Win-specific "MozillaBuild" environment in which Python is running, which is
# spawned from the MozillaBuild script for 64-bit compilers, e.g. start-msvc10-x64.bat
isMozBuild64 = isWin and '64' in os.environ['MOZ_MSVCBITS']  # For MozillaBuild 2.0.0

noMinidumpMsg = r'''
WARNING: Minidumps are not being generated, so all crashes will be uninteresting.
WARNING: Make sure the following key value exists in this key:
WARNING: HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps
WARNING: Name: DumpType  Type: REG_DWORD
WARNING: http://msdn.microsoft.com/en-us/library/windows/desktop/bb787181%28v=vs.85%29.aspx
'''

########################
#  Platform Detection  #
########################


def macVer():
    '''
    If system is a Mac, return the mac type.
    '''
    assert platform.system() == 'Darwin'
    return [int(x) for x in platform.mac_ver()[0].split('.')]


def getFreeSpace(folder, mulVar):
    '''
    Return folder/drive free space in bytes if mulVar is 0.
    Adapted from http://stackoverflow.com/a/2372171
    '''
    assert mulVar >= 0
    if platform.system() == 'Windows':
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(folder), None, None, ctypes.pointer(free_bytes))
        retVal = float(free_bytes.value)
    else:
        retVal = float(os.statvfs(folder).f_bfree * os.statvfs(folder).f_frsize)

    return retVal / (1024 ** mulVar)


#####################
#  Shell Functions  #
#####################


def captureStdout(inputCmd, ignoreStderr=False, combineStderr=False, ignoreExitCode=False,
                  currWorkingDir=os.getcwdu(), env='NOTSET', verbosity=False):
    '''
    Captures standard output, returns the output as a string, along with the return value.
    '''
    if env == 'NOTSET':
        vdump(shellify(inputCmd))
        env = os.environ
    else:
        # There is no way yet to only print the environment variables that were added by the harness
        # We could dump all of os.environ but it is too much verbose output.
        vdump('ENV_VARIABLES_WERE_ADDED_HERE ' + shellify(inputCmd))
    cmd = []
    for el in inputCmd:
        if el.startswith('"') and el.endswith('"'):
            cmd.append(str(el[1:-1]))
        else:
            cmd.append(str(el))
    assert cmd != []
    try:
        p = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if combineStderr else subprocess.PIPE,
            cwd=currWorkingDir,
            env=env)
        (stdout, stderr) = p.communicate()
    except OSError, e:
        raise Exception(repr(e.strerror) + ' error calling: ' + shellify(cmd))
    if p.returncode != 0:
        oomErrorOutput = stdout if combineStderr else stderr
        if (isLinux or isMac) and oomErrorOutput:
            if 'internal compiler error: Killed (program cc1plus)' in oomErrorOutput:
                raise Exception('GCC running out of memory')
            elif 'error: unable to execute command: Killed' in oomErrorOutput:
                raise Exception('Clang running out of memory')
        if not ignoreExitCode:
            # Potential problem area: Note that having a non-zero exit code does not mean that the
            # operation did not succeed, for example when compiling a shell. A non-zero exit code
            # can appear even though a shell compiled successfully.
            # Pymake in builds earlier than revision 232553f741a0 did not support the '-s' option.
            if 'no such option: -s' not in stdout:
                print 'Nonzero exit code from: '
                print '  ' + shellify(cmd)
                print 'stdout is:'
                print stdout
            if stderr is not None:
                print 'stderr is:'
                print stderr
            # Pymake in builds earlier than revision 232553f741a0 did not support the '-s' option.
            if 'hg pull: option --rebase not recognized' not in stdout and 'no such option: -s' not in stdout:
                if isWin and stderr and 'Permission denied' in stderr and \
                        'configure: error: installation or configuration problem: ' + \
                        'C++ compiler cannot create executables.' in stderr:
                    raise Exception('Windows conftest.exe configuration permission problem')
                else:
                    raise Exception('Nonzero exit code')
    if not combineStderr and not ignoreStderr and len(stderr) > 0:
        # Ignore hg color mode throwing an error in console on Windows platforms.
        if not (isWin and 'warning: failed to set color mode to win32' in stderr):
            print 'Unexpected output on stderr from: '
            print '  ' + shellify(cmd)
            print stdout, stderr
            raise Exception('Unexpected output on stderr')
    if stderr and ignoreStderr and len(stderr) > 0 and p.returncode != 0:
        # During configure, there will always be stderr. Sometimes this stderr causes configure to
        # stop the entire script, especially on Windows.
        print 'Return code not zero, and unexpected output on stderr from: '
        print '  ' + shellify(cmd)
        print stdout, stderr
        raise Exception('Return code not zero, and unexpected output on stderr')
    if verbose or verbosity:
        print stdout
        if stderr is not None:
            print stderr
    return stdout.rstrip(), p.returncode


def createWtmpDir(tmpDirBase):
    '''Create wtmp<number> directory, incrementing the number if one is already found.'''
    i = 1
    while True:
        tmpDirWithNum = 'wtmp' + str(i)
        tmpDir = os.path.join(tmpDirBase, tmpDirWithNum)
        try:
            os.mkdir(tmpDir)  # To avoid race conditions, we use try/except instead of exists/create
            break
        except OSError:
            i += 1
    vdump(tmpDirWithNum + os.sep)  # Even if not verbose, wtmp<num> is also dumped: wtmp1/w1: NORMAL
    return tmpDirWithNum


def dateStr():
    '''Equivalent of running `date` in bash, excluding the timezone.'''
    # Try not to add the timezone. Python does not seem to be accurate about DST switchovers.
    # assert captureStdout(['date'])[0] == currDateTime # This fails on Windows
    # On Windows, there is a leading zero in the day of the date in time.asctime()
    return time.asctime()


def disableCorefile():
    '''When called as a preexec_fn, sets appropriate resource limits for the JS shell. Must only be called on POSIX.'''
    import resource  # module only available on POSIX
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def getCoreLimit():
    import resource  # module only available on POSIX
    return resource.getrlimit(resource.RLIMIT_CORE)


def grabMacCrashLog(progname, crashedPID, logPrefix, useLogFiles):
    '''Finds the required crash log in the given crash reporter directory.'''
    assert platform.system() == 'Darwin' and macVer() >= [10, 6]
    reportDirList = [os.path.expanduser('~'), '/']
    for baseDir in reportDirList:
        # Sometimes the crash reports end up in the root directory.
        # This possibly happens when the value of <value>:
        #     defaults write com.apple.CrashReporter DialogType <value>
        # is none, instead of server, or some other option.
        # It also happens when ssh'd into a computer.
        # And maybe when the computer is under heavy load.
        # See http://en.wikipedia.org/wiki/Crash_Reporter_%28Mac_OS_X%29
        reportDir = os.path.join(baseDir, 'Library/Logs/DiagnosticReports/')
        # Find a crash log for the right process name and pid, preferring
        # newer crash logs (which sort last).
        if os.path.exists(reportDir):
            crashLogs = os.listdir(reportDir)
        else:
            crashLogs = []
        # Firefox sometimes still runs as firefox-bin, at least on Mac (likely bug 658850)
        crashLogs = [x for x in crashLogs
                     if x.startswith(progname + '_') or x.startswith(progname + '-bin_')]
        crashLogs.sort(reverse=True)
        for fn in crashLogs:
            fullfn = os.path.join(reportDir, fn)
            try:
                with open(fullfn) as c:
                    firstLine = c.readline()
                if firstLine.rstrip().endswith("[" + str(crashedPID) + "]"):
                    if useLogFiles:
                        # Copy, don't rename, because we might not have permissions
                        # (especially for the system rather than user crash log directory)
                        # Use copyfile, as we do not want to copy the permissions metadata over
                        shutil.copyfile(fullfn, logPrefix + "-crash.txt")
                        captureStdout(["chmod", "og+r", logPrefix + "-crash.txt"])
                        return logPrefix + "-crash.txt"
                    else:
                        return fullfn
                        #return open(fullfn).read()

            except (OSError, IOError):
                # Maybe the log was rotated out between when we got the list
                # of files and when we tried to open this file.  If so, it's
                # clearly not The One.
                pass
    return None


def grabCrashLog(progfullname, crashedPID, logPrefix, wantStack):
    '''Returns the crash log if found.'''
    progname = os.path.basename(progfullname)

    useLogFiles = isinstance(logPrefix, str)
    if useLogFiles:
        if os.path.exists(logPrefix + "-crash.txt"):
            os.remove(logPrefix + "-crash.txt")
        if os.path.exists(logPrefix + "-core"):
            os.remove(logPrefix + "-core")

    if not wantStack or progname == "valgrind":
        return

    # This has only been tested on 64-bit Windows 7 and higher, but should work on 64-bit Vista.
    if isWinVistaOrHigher and isWin64:
        debuggerCmd = constructCdbCommand(progfullname, crashedPID)
    elif os.name == 'posix':
        debuggerCmd = constructGdbCommand(progfullname, crashedPID)
    else:
        debuggerCmd = None

    if debuggerCmd:
        vdump(' '.join(debuggerCmd))
        coreFile = debuggerCmd[-1]
        assert os.path.isfile(coreFile)
        debuggerExitCode = subprocess.call(
            debuggerCmd,
            stdin=None,
            stderr=subprocess.STDOUT,
            stdout=open(logPrefix + "-crash.txt", 'w') if useLogFiles else None,
            # It would be nice to use this everywhere, but it seems to be broken on Windows
            # (http://docs.python.org/library/subprocess.html)
            close_fds=(os.name == "posix"),
            preexec_fn=(disableCorefile if os.name == 'posix' else None)  # Do not generate a corefile if gdb crashes
        )
        if debuggerExitCode != 0:
            print 'Debugger exited with code %d : %s' % (debuggerExitCode, shellify(debuggerCmd))
        if useLogFiles:
            shutil.move(coreFile, logPrefix + "-core")
            subprocess.call(["gzip", '-f', logPrefix + "-core"])
            # chmod here, else the uploaded -core.gz files do not have sufficient permissions.
            subprocess.check_call(['chmod', 'og+r', logPrefix + "-core.gz"])
            return logPrefix + "-crash.txt"
        else:
            print "I don't know what to do with a core file when logPrefix is null"

    # On Mac, look for a crash log generated by Mac OS X Crash Reporter
    elif isMac:
        loops = 0
        maxLoops = 500 if progname.startswith("firefox") else 30
        while True:
            cLogFound = grabMacCrashLog(progname, crashedPID, logPrefix, useLogFiles)
            if cLogFound is not None:
                return cLogFound

            # print "[grabCrashLog] Waiting for the crash log to appear..."
            time.sleep(0.200)
            loops += 1
            if loops > maxLoops:
                # I suppose this might happen if the process corrupts itself so much that
                # the crash reporter gets confused about the process name, for example.
                print "grabCrashLog waited a long time, but a crash log for " + progname + \
                    " [" + str(crashedPID) + "] never appeared!"
                break

    elif isLinux:
        print "Warning: grabCrashLog() did not find a core file for PID %d." % crashedPID
        print "Note: Your soft limit for core file sizes is currently %d. You can increase it with 'ulimit -c' in bash." % getCoreLimit()[0]


def constructCdbCommand(progfullname, crashedPID):
    '''
    Constructs a command that uses the Windows debugger (cdb.exe) to turn a minidump file into a
    stack trace.
    '''
    # On Windows Vista and above, look for a minidump.
    dumpFilename = normExpUserPath(os.path.join(
        '~', 'AppData', 'Local', 'CrashDumps', os.path.basename(progfullname) + '.' + str(crashedPID) + '.dmp'))
    win64bitDebuggerFolder = os.path.join(os.getenv('PROGRAMW6432'), 'Debugging Tools for Windows (x64)')
    # 64-bit cdb.exe seems to also be able to analyse 32-bit binary dumps.
    cdbPath = os.path.join(win64bitDebuggerFolder, 'cdb.exe')
    if not os.path.exists(cdbPath):
        print '\nWARNING: cdb.exe is not found - all crashes will be interesting.\n'
        return None

    if isWinDumpingToDefaultLocation():
        loops = 0
        maxLoops = 300
        while True:
            if os.path.exists(dumpFilename):
                debuggerCmdPath = getAbsPathForAdjacentFile('cdbCmds.txt')
                assert os.path.exists(debuggerCmdPath)

                cdbCmdList = []
                bExploitableDLL = os.path.join(win64bitDebuggerFolder, 'winext', 'msec.dll')
                if os.path.exists(bExploitableDLL):
                    cdbCmdList.append('.load ' + bExploitableDLL)
                cdbCmdList.append('$<' + debuggerCmdPath)

                # See bug 902706 about -g.
                return [cdbPath, '-g', '-c', ';'.join(cdbCmdList), '-z', dumpFilename]

            time.sleep(0.200)
            loops += 1
            if loops > maxLoops:
                # Windows may take some time to generate the dump.
                print "constructCdbCommand waited a long time, but " + dumpFilename + " never appeared!"
                return None
    else:
        return None


def isWinDumpingToDefaultLocation():
    '''Checks whether Windows minidumps are enabled and set to go to Windows' default location.'''
    import _winreg
    # For now, this code does not edit the Windows Registry because we tend to be in a 32-bit
    # version of Python and if one types in regedit in the Run dialog, opens up the 64-bit registry.
    # If writing a key, we most likely need to flush. For the moment, no keys are written.
    try:
        with _winreg.OpenKey(_winreg.ConnectRegistry(None, _winreg.HKEY_LOCAL_MACHINE),
                             r'Software\Microsoft\Windows\Windows Error Reporting\LocalDumps',
                             # Read key from 64-bit registry, which also works for 32-bit
                             0, (_winreg.KEY_WOW64_64KEY + _winreg.KEY_READ)) as key:

            try:
                dumpTypeRegValue = _winreg.QueryValueEx(key, 'DumpType')
                if not (dumpTypeRegValue[0] == 1 and dumpTypeRegValue[1] == _winreg.REG_DWORD):
                    print noMinidumpMsg
                    return False
            except WindowsError as e:
                if e.errno == 2:
                    print noMinidumpMsg
                    return False
                else:
                    raise

            try:
                dumpFolderRegValue = _winreg.QueryValueEx(key, 'DumpFolder')
                # %LOCALAPPDATA%\CrashDumps is the default location.
                if not (dumpFolderRegValue[0] == '%LOCALAPPDATA%\CrashDumps' and
                        dumpFolderRegValue[1] == _winreg.REG_EXPAND_SZ):
                    print '\nWARNING: Dumps are instead appearing at: ' + dumpFolderRegValue[0] + \
                        ' - all crashes will be uninteresting.\n'
                    return False
            except WindowsError as e:
                # If the key value cannot be found, the dumps will be put in the default location
                if e.errno == 2 and e.strerror == 'The system cannot find the file specified':
                    return True
                else:
                    raise

        return True
    except WindowsError as e:
        # If the LocalDumps registry key cannot be found, dumps will be put in the default location.
        if e.errno == 2 and e.strerror == 'The system cannot find the file specified':
            print '\nWARNING: The registry key HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\' + \
                'Windows\\Windows Error Reporting\\LocalDumps cannot be found.\n'
            return None
        else:
            raise


def constructGdbCommand(progfullname, crashedPID):
    '''
    Constructs a command that uses the POSIX debugger (gdb) to turn a minidump file into a
    stack trace.
    '''
    # On Mac and Linux, look for a core file.
    coreFilename = None
    if isMac:
        # Core files will be generated if you do:
        #   mkdir -p /cores/
        #   ulimit -c 2147483648 (or call resource.setrlimit from a preexec_fn hook)
        coreFilename = "/cores/core." + str(crashedPID)
    elif isLinux:
        isPidUsed = False
        if os.path.exists('/proc/sys/kernel/core_uses_pid'):
            with open('/proc/sys/kernel/core_uses_pid') as f:
                isPidUsed = bool(int(f.read()[0]))  # Setting [0] turns the input to a str.
        coreFilename = 'core.' + str(crashedPID) if isPidUsed else 'core'  # relative path
        if not os.path.isfile(coreFilename):
            coreFilename = normExpUserPath(os.path.join('~', coreFilename))  # try the home dir

    if coreFilename and os.path.exists(coreFilename):
        debuggerCmdPath = getAbsPathForAdjacentFile('gdb-quick.txt')
        assert os.path.exists(debuggerCmdPath)

        # Run gdb and move the core file. Tip: gdb gives more info for:
        # (debug with intact build dir > debug > opt with frame pointers > opt)
        return ["gdb", "-n", "-batch", "-x", debuggerCmdPath, progfullname, coreFilename]
    else:
        return None


def getAbsPathForAdjacentFile(filename):
    '''Gets the absolute path of a particular file, given its base directory and filename.'''
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def isProgramInstalled(program):
    '''Checks if the specified program is installed.'''
    whichExit = captureStdout(['which', program], ignoreStderr=True, combineStderr=True, ignoreExitCode=True)[1]
    return whichExit == 0


def rmDirIfEmpty(eDir):
    '''Remove directory if empty.'''
    assert os.path.isdir(eDir)
    if not os.listdir(eDir):
        os.rmdir(eDir)


def rmTreeIfExists(dirTree):
    '''Remove a directory with all sub-directories and files if the directory exists.'''
    if os.path.isdir(dirTree):
        rmTreeIncludingReadOnly(dirTree)
    assert not os.path.isdir(dirTree)


def rmTreeIncludingReadOnly(dirTree):
    shutil.rmtree(dirTree, onerror=handleRemoveReadOnly)


def test_rmTreeIncludingReadOnly():
    '''Run this function in the same directory as subprocesses.py to test.'''
    testDir = 'test_rmTreeIncludingReadOnly'
    os.mkdir(testDir)
    readOnlyDir = os.path.join(testDir, 'nestedReadOnlyDir')
    os.mkdir(readOnlyDir)
    filename = os.path.join(readOnlyDir, 'test.txt')
    with open(filename, 'wb') as f:
        f.write('testing\n')

    os.chmod(filename, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    os.chmod(readOnlyDir, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    rmTreeIncludingReadOnly(testDir)  # Should pass here


def handleRemoveReadOnly(func, path, exc):
    '''Handle read-only files. Adapted from http://stackoverflow.com/q/1213706'''
    if func in (os.rmdir, os.remove) and exc[1].errno == errno.EACCES:
        if os.name == 'posix':
            # Ensure parent directory is also writeable.
            pardir = os.path.abspath(os.path.join(path, os.path.pardir))
            if not os.access(pardir, os.W_OK):
                os.chmod(pardir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        elif os.name == 'nt':
            os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 0777
        func(path)
    else:
        raise


def normExpUserPath(p):
    return os.path.normpath(os.path.expanduser(p))


def shellify(cmd):
    """Try to convert an arguments array to an equivalent string that can be pasted into a shell."""
    okUnquotedRE = re.compile(r"""^[a-zA-Z0-9\-\_\.\,\/\=\~@\+]*$""")
    okQuotedRE = re.compile(r"""^[a-zA-Z0-9\-\_\.\,\/\=\~@\{\}\|\(\)\+ ]*$""")
    ssc = []
    for i in xrange(len(cmd)):
        item = cmd[i]
        if okUnquotedRE.match(item):
            ssc.append(item)
        elif okQuotedRE.match(item):
            ssc.append('"' + item + '"')
        else:
            vdump('Regex not matched, but trying to shellify anyway:')
            return ' '.join(cmd).replace('\\', '//') if isWin else ' '.join(cmd)
    return ' '.join(ssc)


def timeSubprocess(command, ignoreStderr=False, combineStderr=False, ignoreExitCode=False,
                   cwd=os.getcwdu(), env=os.environ, vb=False):
    '''
    Calculates how long a captureStdout command takes and prints it. Returns the stdout and return
    value that captureStdout passes on.
    '''
    print 'Running `%s` now..' % shellify(command)
    startTime = time.time()
    stdOutput, retVal = captureStdout(command, ignoreStderr=ignoreStderr,
                                      combineStderr=combineStderr, ignoreExitCode=ignoreExitCode,
                                      currWorkingDir=cwd, env=env, verbosity=vb)
    endTime = time.time()
    print '`' + shellify(command) + '` took %.3f seconds.\n' % (endTime - startTime)
    return stdOutput, retVal


class Unbuffered:
    '''From http://stackoverflow.com/a/107717 - Unbuffered stdout by default, similar to -u.'''

    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        self.stream.write(data)
        self.stream.flush()

    def __getattr__(self, attr):
        return getattr(self.stream, attr)


def vdump(inp):
    '''
    This function appends the word 'DEBUG' to any verbose output.
    '''
    if verbose:
        print 'DEBUG -', inp


###########
#  Tests  #
###########

if __name__ == '__main__':
    vdump('Running tests...')
    assert isProgramInstalled('date')
    assert not isProgramInstalled('FOOBARFOOBAR')
    vdump('Done')

# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Functions dealing with files and their contents.
"""

import io
import os
from pathlib import Path
import platform
from shlex import quote
import shutil
import subprocess
import time

from pkg_resources import parse_version

from .logging_helpers import get_logger

LOG_OS_OPS = get_logger(__name__)

NO_DUMP_MSG = r"""
Minidumps are not being generated, so all crashes will be uninteresting.
Make sure the following key value exists in this key:
HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps
Name: DumpType  Type: REG_DWORD
http://msdn.microsoft.com/en-us/library/windows/desktop/bb787181%28v=vs.85%29.aspx
"""


def make_cdb_cmd(prog_full_path, crashed_pid):
    """Construct a command that uses the Windows debugger (cdb.exe) to turn a minidump file into a stack trace.

    Args:
        prog_full_path (Path): Full path to the program
        crashed_pid (int): PID of the program

    Returns:
        list: cdb command list
    """
    assert platform.system() == "Windows"
    # Look for a minidump.
    dump_name = Path.home() / "AppData" / "Local" / "CrashDumps" / f"{prog_full_path.name}.{crashed_pid}.dmp"

    if platform.uname()[2] == "10":  # Windows 10
        win64_debugging_folder = Path(os.getenv("PROGRAMFILES(X86)")) / "Windows Kits" / "10" / "Debuggers" / "x64"
    else:
        win64_debugging_folder = Path(os.getenv("PROGRAMW6432")) / "Debugging Tools for Windows (x64)"

    # 64-bit cdb.exe seems to also be able to analyse 32-bit binary dumps.
    cdb_path = win64_debugging_folder / "cdb.exe"
    if not cdb_path.is_file():
        LOG_OS_OPS.warning("")
        LOG_OS_OPS.warning("cdb.exe is not found - all crashes will be interesting.")
        LOG_OS_OPS.warning("")
        return []

    if is_win_dumping_to_default():
        loops = 0
        max_loops = 300
        while True:
            if dump_name.is_file():
                dbggr_cmd_path = Path(__file__).parent / "cdb_cmds.txt"
                assert dbggr_cmd_path.is_file()

                cdb_cmd_list = []
                cdb_cmd_list.append(f"$<{dbggr_cmd_path}")

                # See bug 902706 about -g.
                return [cdb_path, "-g", "-c", ";".join(cdb_cmd_list), "-z", str(dump_name)]

            time.sleep(0.200)
            loops += 1
            if loops > max_loops:
                # Windows may take some time to generate the dump.
                LOG_OS_OPS.warning("make_cdb_cmd waited a long time, but %s never appeared!", dump_name)
                return []
    else:
        return []


def make_gdb_cmd(prog_full_path, crashed_pid):
    """Construct a command that uses the POSIX debugger (gdb) to turn a minidump file into a stack trace.

    Args:
        prog_full_path (Path): Full path to the program
        crashed_pid (int): PID of the program

    Returns:
        list: gdb command list
    """
    assert os.name == "posix"
    # On Mac and Linux, look for a core file.
    core_name = ""
    core_name_path = Path()
    if platform.system() == "Darwin":
        # Core files will be generated if you do:
        #   mkdir -p /cores/
        #   ulimit -c 2147483648 (or call resource.setrlimit from a preexec_fn hook)
        core_name = f"/cores/core.{crashed_pid}"
        core_name_path = Path(core_name)
    elif platform.system() == "Linux":
        is_pid_used = False
        core_uses_pid_path = Path("/proc/sys/kernel/core_uses_pid")
        if core_uses_pid_path.is_file():
            with io.open(str(core_uses_pid_path), "r", encoding="utf-8", errors="replace") as f:
                is_pid_used = bool(int(f.read()[0]))  # Setting [0] turns the input to a str.
        core_name = f"core.{crashed_pid}" if is_pid_used else "core"
        core_name_path = Path.cwd() / core_name
        if not core_name_path.is_file():  # try the home dir
            core_name_path = Path.home() / core_name

    if core_name and core_name_path.is_file():
        dbggr_cmd_path = Path(__file__).parent / "gdb_cmds.txt"
        assert dbggr_cmd_path.is_file()

        # Run gdb and move the core file. Tip: gdb gives more info for:
        # (debug with intact build dir > debug > opt with frame pointers > opt)
        return ["gdb", "-n", "-batch", "-x", str(dbggr_cmd_path), str(prog_full_path), str(core_name)]
    return []


def disable_corefile():
    """When called as a preexec_fn, sets appropriate resource limits for the JS shell. Must only be called on POSIX."""
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except ImportError:
        return


def get_core_limit():
    """Returns the maximum core file size that the current process can create.

    Returns:
        int: Maximum size (in bytes) of a core file that the current process can create.
    """
    try:
        import resource
        return resource.getrlimit(resource.RLIMIT_CORE)
    except ImportError:
        return None


# pylint: disable=inconsistent-return-statements
def grab_crash_log(prog_full_path, crashed_pid, log_prefix, want_stack):
    # pylint: disable=too-complex,too-many-branches
    """Return the crash log if found.

    Args:
        prog_full_path (Path): Full path to the program
        crashed_pid (int): PID of the crashed program
        log_prefix (str): Log prefix
        want_stack (bool): Boolean on whether a stack is desired

    Returns:
        str: Returns the path to the crash log
    """
    progname = prog_full_path.name

    use_logfiles = isinstance(log_prefix, ("".__class__, u"".__class__, b"".__class__, Path))
    crash_log = (log_prefix.parent / f"{log_prefix.stem}-crash").with_suffix(".txt")
    core_file = log_prefix.parent / f"{log_prefix.stem}-core"

    if use_logfiles:
        if crash_log.is_file():
            crash_log.unlink()
        if core_file.is_file():
            core_file.unlink()

    if not want_stack or progname == "valgrind":
        return ""

    # This has only been tested on 64-bit Windows 7 and higher
    if platform.system() == "Windows":
        dbggr_cmd = make_cdb_cmd(prog_full_path, crashed_pid)
    elif os.name == "posix":
        dbggr_cmd = make_gdb_cmd(prog_full_path, crashed_pid)
    else:
        dbggr_cmd = None

    if dbggr_cmd:
        LOG_OS_OPS.info(" ".join([str(x) for x in dbggr_cmd]))
        core_file = Path(dbggr_cmd[-1])
        assert core_file.is_file()
        try:
            dbbgr_exit_code = subprocess.run(
                [str(x) for x in dbggr_cmd],
                check=True,
                stdin=None,
                stderr=subprocess.STDOUT,
                stdout=io.open(str(crash_log), "w", encoding="utf-8", errors="replace") if use_logfiles else None,
                # It would be nice to use this everywhere, but it seems to be broken on Windows
                # (http://docs.python.org/library/subprocess.html)
                close_fds=(os.name == "posix"),
                # Do not generate a core_file if gdb crashes in Linux
                preexec_fn=(disable_corefile if platform.system() == "Linux" else None),
            )
        except subprocess.CalledProcessError:
            LOG_OS_OPS.info("Debugger exited with code %s : %s",
                            dbbgr_exit_code, " ".join(quote(str(x)) for x in dbggr_cmd))
        if use_logfiles:  # pylint: disable=no-else-return
            if core_file.is_file():
                shutil.move(str(core_file), str(core_file))
                subprocess.run(["gzip", "-f", str(core_file)], check=True)
                # chmod here, else the uploaded -core.gz files do not have sufficient permissions.
                gzipped_core = Path(f"{core_file}.gz")
                # Ensure gzipped file can be read by all
                Path.chmod(gzipped_core, Path.stat(gzipped_core).st_mode | 0o444)
            return str(crash_log)
        else:
            LOG_OS_OPS.warning("I don't know what to do with a core file when log_prefix is null")

    # On Mac, look for a crash log generated by Mac OS X Crash Reporter
    elif platform.system() == "Darwin":
        loops = 0
        max_loops = 450
        while True:
            crash_log_found = grab_mac_crash_log(crashed_pid, log_prefix, use_logfiles)
            if crash_log_found is not None:
                return crash_log_found

            # LOG_OS_OPS.info("[grab_crash_log] Waiting for the crash log to appear...")
            time.sleep(0.200)
            loops += 1
            if loops > max_loops:
                # I suppose this might happen if the process corrupts itself so much that
                # the crash reporter gets confused about the process name, for example.
                LOG_OS_OPS.warning("grab_crash_log waited a long time, but a crash log for %s [%s] never appeared!",
                                   progname, crashed_pid)
                break

    elif platform.system() == "Linux":
        LOG_OS_OPS.warning("grab_crash_log() did not find a core file for PID %s.", crashed_pid)
        LOG_OS_OPS.warning("Your soft limit for core file sizes is currently %s. "
                           'You can increase it with "ulimit -c" in bash.', get_core_limit()[0])


def grab_mac_crash_log(crash_pid, log_prefix, use_log_files):
    """Find the required crash log in the given crash reporter directory.

    Args:
        crash_pid (str): PID value of the crashed process
        log_prefix (str): Prefix (may include dirs) of the log file
        use_log_files (bool): Boolean that decides whether *-crash.txt log files should be used

    Returns:
        str: Absolute (if use_log_files is False) or relative (if use_log_files is True) path to crash log file
    """
    assert parse_version(platform.mac_ver()[0]) >= parse_version("10.6")

    for base_dir in [Path.home(), Path("/")]:
        # Sometimes the crash reports end up in the root directory.
        # This possibly happens when the value of <value>:
        #     defaults write com.apple.CrashReporter DialogType <value>
        # is none, instead of server, or some other option.
        # It also happens when ssh'd into a computer.
        # And maybe when the computer is under heavy load.
        # See http://en.wikipedia.org/wiki/Crash_Reporter_%28Mac_OS_X%29
        reports_dir = base_dir / "Library" / "Logs" / "DiagnosticReports"
        # Find a crash log for the right process name and pid, preferring
        # newer crash logs (which sort last).
        if reports_dir.is_dir():
            crash_logs = sorted(list(reports_dir.iterdir()), reverse=True)
        else:
            crash_logs = []

        for file_name in (x for x in crash_logs if crash_logs):
            full_report_path = reports_dir / file_name
            try:
                with io.open(str(full_report_path), "r", encoding="utf-8", errors="replace") as f:
                    first_line = f.readline()
                if first_line.rstrip().endswith(f"[{crash_pid}]"):
                    if use_log_files:
                        # Copy, don't rename, because we might not have permissions
                        # (especially for the system rather than user crash log directory)
                        # Use copyfile, as we do not want to copy the permissions metadata over
                        crash_log = (log_prefix.parent / f"{log_prefix.stem}-crash").with_suffix(".txt")
                        shutil.copyfile(str(full_report_path), str(crash_log))
                        # Ensure crash_log can be read by all
                        Path.chmod(crash_log, Path.stat(crash_log).st_mode | 0o444)
                        return str(crash_log)
                    return str(full_report_path)

            except OSError:
                # Maybe the log was rotated out between when we got the list
                # of files and when we tried to open this file.  If so, it's
                # clearly not The One.
                pass
    return None


def is_win_dumping_to_default():  # pylint: disable=too-complex
    """Check whether Windows minidumps are enabled and set to go to Windows' default location.

    Raises:
        OSError: Raises if querying for the DumpType key throws and it is unrelated to various issues,
                 e.g. the key not being present.

    Returns:
        bool: Returns True when Windows has dumping enabled, and is dumping to the default location, otherwise False
    """
    import winreg  # pylint: disable=import-error
    # For now, this code does not edit the Windows Registry because we tend to be in a 32-bit
    # version of Python and if one types in regedit in the Run dialog, opens up the 64-bit registry.
    # If writing a key, we most likely need to flush. For the moment, no keys are written.
    try:
        with winreg.OpenKey(winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE),
                            r"Software\Microsoft\Windows\Windows Error Reporting\LocalDumps",
                            # Read key from 64-bit registry, which also works for 32-bit
                            0, (winreg.KEY_WOW64_64KEY + winreg.KEY_READ)) as key:

            try:
                dump_type_reg_value = winreg.QueryValueEx(key, "DumpType")
                if not (dump_type_reg_value[0] == 1 and dump_type_reg_value[1] == winreg.REG_DWORD):
                    LOG_OS_OPS.warning(NO_DUMP_MSG)
                    return False
            except OSError as ex:
                if ex.errno == 2:  # pylint: disable=no-else-return
                    LOG_OS_OPS.warning(NO_DUMP_MSG)
                    return False
                else:
                    raise

            try:
                dump_folder_reg_value = winreg.QueryValueEx(key, "DumpFolder")
                # %LOCALAPPDATA%\CrashDumps is the default location.
                if not (dump_folder_reg_value[0] == r"%LOCALAPPDATA%\CrashDumps" and
                        dump_folder_reg_value[1] == winreg.REG_EXPAND_SZ):
                    LOG_OS_OPS.warning("")
                    LOG_OS_OPS.warning("Dumps are instead appearing at: %s - "
                                       "all crashes will be uninteresting.", dump_folder_reg_value[0])
                    LOG_OS_OPS.warning("")
                    return False
            except OSError as ex:
                # If the key value cannot be found, the dumps will be put in the default location
                # pylint: disable=no-else-return
                if ex.errno == 2 and ex.strerror == "The system cannot find the file specified":
                    return True
                else:
                    raise

        return True
    except OSError as ex:
        # If the LocalDumps registry key cannot be found, dumps will be put in the default location.
        # pylint: disable=no-else-return
        if ex.errno == 2 and ex.strerror == "The system cannot find the file specified":
            LOG_OS_OPS.warning("")
            LOG_OS_OPS.warning("The registry key HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\"
                               "Windows\\Windows Error Reporting\\LocalDumps cannot be found.")
            LOG_OS_OPS.warning("")
            return False
        else:
            raise


def make_wtmp_dir(base_dir):
    """Create wtmp<number> directory, incrementing the number if one is already found.

    Args:
        base_dir (Path): Base directory to create the wtmp directories

    Returns:
        Path: Full path to the numbered wtmp directory
    """
    assert isinstance(base_dir, Path)

    i = 1
    while True:
        numbered_tmp_dir = f"wtmp{i}"
        full_dir = base_dir / numbered_tmp_dir
        try:
            full_dir.mkdir()  # To avoid race conditions, we use try/except instead of exists/create
            break  # break out of the while loop
        except OSError:
            i += 1

    return full_dir

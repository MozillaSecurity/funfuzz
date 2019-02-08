# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Helper functions dealing with the files on the file system.
"""

import errno
from pathlib import Path
import platform
import shutil
import stat


def delete_logs(log_prefix):  # pylint: disable=too-complex
    """Whoever might call baseLevel should eventually call this function (unless a bug was found).

    If this turns up a WindowsError on Windows, remember to have excluded fuzzing locations in
    the search indexer, anti-virus realtime protection and backup applications.

    Args:
        log_prefix (Path): Prefix of the log name
    """
    out_log = (log_prefix.parent / f"{log_prefix.stem}-out").with_suffix(".txt")
    if out_log.is_file():
        out_log.unlink()
    if out_log.with_suffix(".binaryen-seed").is_file():
        out_log.with_suffix(".binaryen-seed").unlink()
    if out_log.with_suffix(".wasm").is_file():
        out_log.with_suffix(".wasm").unlink()
    if out_log.with_suffix(".wrapper").is_file():
        out_log.with_suffix(".wrapper").unlink()
    err_log = (log_prefix.parent / f"{log_prefix.stem}-err").with_suffix(".txt")
    if err_log.is_file():
        err_log.unlink()
    wasm_err_log = (log_prefix.parent / f"{log_prefix.stem}-wasm-err").with_suffix(".txt")
    if wasm_err_log.is_file():
        wasm_err_log.unlink()
    wasm_out_log = (log_prefix.parent / f"{log_prefix.stem}-wasm-out").with_suffix(".txt")
    if wasm_out_log.is_file():
        wasm_out_log.unlink()
    wasm_summary_log = (log_prefix.parent / f"{log_prefix.stem}-wasm-summary").with_suffix(".txt")
    if wasm_summary_log.is_file():
        wasm_summary_log.unlink()
    crash_log = (log_prefix.parent / f"{log_prefix.stem}-crash").with_suffix(".txt")
    if crash_log.is_file():
        crash_log.unlink()
    valgrind_xml = (log_prefix.parent / f"{log_prefix.stem}-vg").with_suffix(".xml")
    if valgrind_xml.is_file():
        valgrind_xml.unlink()
    core_gzip = (log_prefix.parent / f"{log_prefix.stem}-core").with_suffix(".gz")
    if core_gzip.is_file():
        core_gzip.unlink()


def handle_rm_readonly_files(_func, path, exc):
    """Handle read-only files on Windows. Adapted from https://stackoverflow.com/a/21263493.

    Args:
        _func (function): Function which raised the exception
        path (str): Path name passed to function
        exc (exception): Exception information returned by sys.exc_info()

    Raises:
        OSError: Raised if the read-only files are unable to be handled
    """
    assert platform.system() == "Windows"
    path = Path(path)
    if exc[1].errno == errno.EACCES:
        Path.chmod(path, stat.S_IWRITE)
        assert path.is_file()
        path.unlink()
    else:
        raise OSError("Unable to handle read-only files.")


def rm_tree_incl_readonly_files(dir_tree):
    """Remove a directory tree including all read-only files. Directories should not be read-only.

    Args:
        dir_tree (Path): Directory tree of files to be removed
    """
    shutil.rmtree(str(dir_tree), onerror=handle_rm_readonly_files if platform.system() == "Windows" else None)

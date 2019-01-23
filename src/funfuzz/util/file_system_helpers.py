# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Helper functions dealing with the files on the file system.
"""


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
    crash_log = (log_prefix.parent / f"{log_prefix.stem}-crash").with_suffix(".txt")
    if crash_log.is_file():
        crash_log.unlink()
    valgrind_xml = (log_prefix.parent / f"{log_prefix.stem}-vg").with_suffix(".xml")
    if valgrind_xml.is_file():
        valgrind_xml.unlink()
    core_gzip = (log_prefix.parent / f"{log_prefix.stem}-core").with_suffix(".gz")
    if core_gzip.is_file():
        core_gzip.unlink()

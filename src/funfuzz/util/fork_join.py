# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Functions dealing with multiple processes.
"""

import io
import logging
import multiprocessing
from pathlib import Path

from .logging_helpers import get_logger

LOG_FORK_JOIN = get_logger(__name__)


# Call |fun| in a bunch of separate processes, then wait for them all to finish.
# fun is called with someArgs, plus an additional argument with a numeric ID.
# |fun| must be a top-level function (not a closure) so it can be pickled on Windows.
def forkJoin(logDir, numProcesses, fun, *someArgs):  # pylint: disable=invalid-name,missing-docstring
    def showFile(fn):  # pylint: disable=invalid-name
        LOG_FORK_JOIN.info("==== %s ====", fn)
        LOG_FORK_JOIN.info("")
        with io.open(str(fn), "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                LOG_FORK_JOIN.info(line.rstrip())
        LOG_FORK_JOIN.info("")

    # Fork a bunch of processes
    LOG_FORK_JOIN.info("Forking %s children...", numProcesses)
    ps = []  # pylint: disable=invalid-name
    for i in range(numProcesses):
        p = multiprocessing.Process(  # pylint: disable=invalid-name
            target=redirectOutputAndCallFun, args=[logDir, i, fun, someArgs], name=f"Parallel process {i}")
        p.start()
        ps.append(p)

    # Wait for them all to finish, and splat their outputs
    for i in range(numProcesses):
        p = ps[i]  # pylint: disable=invalid-name
        LOG_FORK_JOIN.info("=== Waiting for child #%s (%s) to finish... ===", i, p.pid)
        p.join()
        LOG_FORK_JOIN.info("=== Child process #%s exited with code %s ===", i, p.exitcode)
        LOG_FORK_JOIN.info("")
        showFile(log_name(logDir, i, "out"))
        showFile(log_name(logDir, i, "err"))
        LOG_FORK_JOIN.info("")


# Functions used by forkJoin are top-level so they can be "pickled" (required on Windows)
def log_name(log_dir, i, log_type):
    """Returns the path of the forkjoin log file as a string.

    Args:
        log_dir (str): Directory of the log file
        i (int): Log number
        log_type (str): Log type

    Returns:
        str: The forkjoin log file path
    """
    return str(Path(log_dir) / f"forkjoin-{i}-{log_type}.txt")


def redirectOutputAndCallFun(logDir, i, fun, someArgs):  # pylint: disable=invalid-name,missing-docstring
    redirect_log = get_logger("redirect-log", level=logging.DEBUG)
    combined_handler = logging.FileHandler(log_name(logDir, i, "combined"))
    combined_handler.setLevel(logging.DEBUG)
    redirect_log.addHandler(combined_handler)
    # sys.stdout = io.open(log_name(logDir, i, "out"), "w", buffering=1)
    # sys.stderr = io.open(log_name(logDir, i, "err"), "w", buffering=1)
    fun(*(someArgs + (i,)))


# You should see:
# * "Green Chairs" from the first few processes
# * A pause and error (with stack trace) from process 5
# * "Green Chairs" again from the rest.
# def test_forkJoin():
#     forkJoin(".", 8, test_forkJoin_inner, "Green", "Chairs")


# def test_forkJoin_inner(adj, noun, forkjoin_id):
#     import time
#     LOG_FORK_JOIN.info("%s %s", adj, noun)
#     LOG_FORK_JOIN.info(forkjoin_id)
#     if forkjoin_id == 5:
#         time.sleep(1)
#         raise NameError()


# if __name__ == "__main__":
#     LOG_FORK_JOIN.info("test_forkJoin():")
#     test_forkJoin()

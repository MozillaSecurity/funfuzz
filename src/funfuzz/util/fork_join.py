# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Functions dealing with multiple processes.
"""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import io
import logging
import multiprocessing
import sys

from past.builtins import range

if sys.version_info.major == 2:
    from pathlib2 import Path
else:
    from pathlib import Path  # pylint: disable=import-error

FUNFUZZ_LOG = logging.getLogger("funfuzz")
logging.basicConfig(level=logging.DEBUG)


# Call |fun| in a bunch of separate processes, then wait for them all to finish.
# fun is called with someArgs, plus an additional argument with a numeric ID.
# |fun| must be a top-level function (not a closure) so it can be pickled on Windows.
def forkJoin(logDir, numProcesses, fun, *someArgs):  # pylint: disable=invalid-name,missing-docstring
    def showFile(fn):  # pylint: disable=invalid-name,missing-docstring
        FUNFUZZ_LOG.info("==== %s ====", fn)
        FUNFUZZ_LOG.info("")
        with io.open(str(fn), "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                FUNFUZZ_LOG.info(line.rstrip())
        FUNFUZZ_LOG.info("")

    # Fork a bunch of processes
    FUNFUZZ_LOG.info("Forking %d children...", numProcesses)
    ps = []  # pylint: disable=invalid-name
    for i in range(numProcesses):
        p = multiprocessing.Process(  # pylint: disable=invalid-name
            target=redirectOutputAndCallFun, args=[logDir, i, fun, someArgs], name="Parallel process " + str(i))
        p.start()
        ps.append(p)

    # Wait for them all to finish, and splat their outputs
    for i in range(numProcesses):
        p = ps[i]  # pylint: disable=invalid-name
        FUNFUZZ_LOG.info("=== Waiting for child #%d (%d) to finish... ===", i, p.pid)
        p.join()
        FUNFUZZ_LOG.info("=== Child process #%d exited with code %d ===", i, p.exitcode)
        FUNFUZZ_LOG.info("")
        showFile(log_name(logDir, i, "out"))
        showFile(log_name(logDir, i, "err"))
        FUNFUZZ_LOG.info("")


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
    return str(Path(log_dir) / ("forkjoin-%s-%s.txt" % (i, log_type)))


def redirectOutputAndCallFun(logDir, i, fun, someArgs):  # pylint: disable=invalid-name,missing-docstring
    sys.stdout = io.open(log_name(logDir, i, "out"), "wb", buffering=0)
    sys.stderr = io.open(log_name(logDir, i, "err"), "wb", buffering=0)
    fun(*(someArgs + (i,)))


# You should see:
# * "Green Chairs" from the first few processes
# * A pause and error (with stack trace) from process 5
# * "Green Chairs" again from the rest.
# def test_forkJoin():
#     forkJoin(".", 8, test_forkJoin_inner, "Green", "Chairs")


# def test_forkJoin_inner(adj, noun, forkjoin_id):
#     import time
#     FUNFUZZ_LOG.info("%s %s", adj, noun)
#     FUNFUZZ_LOG.info(forkjoin_id)
#     if forkjoin_id == 5:
#         time.sleep(1)
#         raise NameError()


# if __name__ == "__main__":
#     FUNFUZZ_LOG.info("test_forkJoin():")
#     test_forkJoin()

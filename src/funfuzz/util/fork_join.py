# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Functions dealing with multiple processes.
"""

import io
import multiprocessing
from pathlib import Path
import sys


# Call |fun| in a bunch of separate processes, then wait for them all to finish.
# fun is called with someArgs, plus an additional argument with a numeric ID.
# |fun| must be a top-level function (not a closure) so it can be pickled on Windows.
def forkJoin(logDir, numProcesses, fun, *someArgs):  # pylint: disable=invalid-name,missing-docstring
    def showFile(fn):  # pylint: disable=invalid-name
        print(f"==== {fn} ====")
        print()
        with io.open(str(fn), "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                print(line.rstrip())
        print()

    # Fork a bunch of processes
    print(f"Forking {numProcesses} children...")
    ps = []  # pylint: disable=invalid-name
    for i in range(numProcesses):
        p = multiprocessing.Process(  # pylint: disable=invalid-name
            target=redirectOutputAndCallFun, args=[logDir, i, fun, someArgs], name=f"Parallel process {i}")
        p.start()
        ps.append(p)

    # Wait for them all to finish, and splat their outputs
    for i in range(numProcesses):
        p = ps[i]  # pylint: disable=invalid-name
        print(f"=== Waiting for child #{i} ({p.pid}) to finish... ===")
        p.join()
        print(f"=== Child process #{i} exited with code {p.exitcode} ===")
        print()
        showFile(log_name(logDir, i, "out"))
        showFile(log_name(logDir, i, "err"))
        print()


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
    sys.stdout = io.open(log_name(logDir, i, "out"), "w", buffering=1)
    sys.stderr = io.open(log_name(logDir, i, "err"), "w", buffering=1)
    fun(*(someArgs + (i,)))


# You should see:
# * "Green Chairs" from the first few processes
# * A pause and error (with stack trace) from process 5
# * "Green Chairs" again from the rest.
# def test_forkJoin():
#     forkJoin(".", 8, test_forkJoin_inner, "Green", "Chairs")


# def test_forkJoin_inner(adj, noun, forkjoin_id):
#     import time
#     print(f"{adj} {noun}")
#     print(forkjoin_id)
#     if forkjoin_id == 5:
#         time.sleep(1)
#         raise NameError()


# if __name__ == "__main__":
#     print("test_forkJoin():")
#     test_forkJoin()

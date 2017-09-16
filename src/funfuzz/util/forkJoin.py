#!/usr/bin/env python
# coding=utf-8
# pylint: disable=invalid-name,missing-docstring
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import absolute_import, print_function

import multiprocessing
import os
import sys


# Call |fun| in a bunch of separate processes, then wait for them all to finish.
# fun is called with someArgs, plus an additional argument with a numeric ID.
# |fun| must be a top-level function (not a closure) so it can be pickled on Windows.
def forkJoin(logDir, numProcesses, fun, *someArgs):
    def showFile(fn):
        print("==== %s ====" % fn)
        print()
        with open(fn) as f:
            for line in f:
                print(line.rstrip())
        print()

    # Fork a bunch of processes
    print("Forking %d children..." % numProcesses)
    ps = []
    for i in range(numProcesses):
        p = multiprocessing.Process(
            target=redirectOutputAndCallFun, args=[logDir, i, fun, someArgs], name="Parallel process " + str(i))
        p.start()
        ps.append(p)

    # Wait for them all to finish, and splat their outputs
    for i in range(numProcesses):
        p = ps[i]
        print("=== Waiting for child #%d (%d) to finish... ===" % (i, p.pid))
        p.join()
        print("=== Child process #%d exited with code %d ===" % (i, p.exitcode))
        print()
        showFile(logFileName(logDir, i, "out"))
        showFile(logFileName(logDir, i, "err"))
        print()


# Functions used by forkJoin are top-level so they can be "pickled" (required on Windows)
def logFileName(logDir, i, t):
    return os.path.join(logDir, "forkjoin-" + str(i) + "-" + t + ".txt")


def redirectOutputAndCallFun(logDir, i, fun, someArgs):
    sys.stdout = open(logFileName(logDir, i, "out"), 'wb', buffering=0)
    sys.stderr = open(logFileName(logDir, i, "err"), 'wb', buffering=0)
    fun(*(someArgs + (i,)))


# You should see:
# * "Green Chairs" from the first few processes
# * A pause and error (with stack trace) from process 5
# * "Green Chairs" again from the rest.
def test_forkJoin():
    forkJoin(".", 8, test_forkJoin_inner, "Green", "Chairs")


def test_forkJoin_inner(adj, noun, forkjoin_id):
    import time
    print("%s %s" % (adj, noun))
    print(forkjoin_id)
    if forkjoin_id == 5:
        time.sleep(1)
        raise NameError()


if __name__ == "__main__":
    print("test_forkJoin():")
    test_forkJoin()

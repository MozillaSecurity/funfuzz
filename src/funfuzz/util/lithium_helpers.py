# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Helper functions to use the Lithium reducer.
"""

from __future__ import absolute_import, print_function

import os
import sys
import shutil
import subprocess
import tempfile

from past.builtins import range  # pylint: disable=redefined-builtin

from . import subprocesses as sps

runlithiumpy = [sys.executable, "-u", "-m", "lithium"]  # pylint: disable=invalid-name

# Status returns for runLithium and many_timed_runs
(HAPPY, NO_REPRO_AT_ALL, NO_REPRO_EXCEPT_BY_URL, LITH_NO_REPRO,
 LITH_FINISHED, LITH_RETESTED_STILL_INTERESTING, LITH_PLEASE_CONTINUE, LITH_BUSTED) = range(8)


def runLithium(lithArgs, logPrefix, targetTime):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Run Lithium as a subprocess: reduce to the smallest file that has at least the same unhappiness level.

    Returns a tuple of (lithlogfn, LITH_*, details).
    """
    deletableLithTemp = None  # pylint: disable=invalid-name
    if targetTime:
        # FIXME: this could be based on whether bot has a remoteHost  # pylint: disable=fixme
        # loop is being used by bot
        deletableLithTemp = tempfile.mkdtemp(prefix="fuzzbot-lithium")  # pylint: disable=invalid-name
        lithArgs = ["--maxruntime=" + str(targetTime), "--tempdir=" + deletableLithTemp] + lithArgs
    else:
        # loop is being run standalone
        lithtmp = logPrefix + "-lith-tmp"
        os.mkdir(lithtmp)
        lithArgs = ["--tempdir=" + lithtmp] + lithArgs
    lithlogfn = logPrefix + "-lith-out.txt"
    print("Preparing to run Lithium, log file %s" % lithlogfn)
    print(sps.shellify(runlithiumpy + lithArgs))
    subprocess.call(runlithiumpy + lithArgs, stdout=open(lithlogfn, "w"), stderr=subprocess.STDOUT)
    print("Done running Lithium")
    if deletableLithTemp:
        shutil.rmtree(deletableLithTemp)
    r = readLithiumResult(lithlogfn)  # pylint: disable=invalid-name
    subprocess.call(["gzip", "-f", lithlogfn])
    return r


def readLithiumResult(lithlogfn):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    with open(lithlogfn) as f:
        for line in f:
            if line.startswith("Lithium result"):
                print(line.rstrip())
            if line.startswith("Lithium result: interesting"):
                return (LITH_RETESTED_STILL_INTERESTING, None)
            elif line.startswith("Lithium result: succeeded, reduced to: "):
                # pylint: disable=invalid-name
                reducedTo = line[len("Lithium result: succeeded, reduced to: "):].rstrip()  # e.g. "4 lines"
                return (LITH_FINISHED, reducedTo)
            elif (line.startswith("Lithium result: not interesting") or
                  line.startswith("Lithium result: the original testcase is not")):
                return (LITH_NO_REPRO, None)
            elif line.startswith("Lithium result: please continue using: "):
                # pylint: disable=invalid-name
                lithiumHint = line[len("Lithium result: please continue using: "):].rstrip()
                return (LITH_PLEASE_CONTINUE, lithiumHint)
        return (LITH_BUSTED, None)

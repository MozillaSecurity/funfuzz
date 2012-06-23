#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import with_statement

import os
import shutil
import subprocess
from tempfile import mkdtemp

from subprocesses import shellify

p0 = os.path.dirname(os.path.abspath(__file__))
lithiumpy = ["python", "-u", os.path.join(p0, os.pardir, "lithium", "lithium.py")]

# Status returns for runLithium and many_timed_runs (in loopdomfuzz.py, etc.)
(HAPPY, NO_REPRO_AT_ALL, NO_REPRO_EXCEPT_BY_URL, LITH_NO_REPRO, LITH_FINISHED, LITH_RETESTED_STILL_INTERESTING, LITH_PLEASE_CONTINUE, LITH_BUSTED) = range(8)

def runLithium(lithArgs, logPrefix, targetTime):
    """
      Run Lithium as a subprocess: reduce to the smallest file that has at least the same unhappiness level.
      Returns a tuple of (lithlogfn, LITH_*, details).
    """
    deletableLithTemp = None
    if targetTime:
        # loopdomfuzz.py is being used by bot.py
        deletableLithTemp = mkdtemp(prefix="domfuzz-ldf-bot")
        lithArgs = ["--maxruntime=" + str(targetTime), "--tempdir=" + deletableLithTemp] + lithArgs
    else:
        # loopdomfuzz.py is being run standalone
        lithtmp = logPrefix + "-lith-tmp"
        os.mkdir(lithtmp)
        lithArgs = ["--tempdir=" + lithtmp] + lithArgs
    lithlogfn = logPrefix + "-lith-out"
    print "Preparing to run Lithium, log file " + lithlogfn
    print shellify(lithiumpy + lithArgs)
    subprocess.call(lithiumpy + lithArgs, stdout=open(lithlogfn, "w"), stderr=subprocess.STDOUT)
    print "Done running Lithium"
    if deletableLithTemp:
        shutil.rmtree(deletableLithTemp)
    r = readLithiumResult(lithlogfn)
    subprocess.call(["gzip", "-f", lithlogfn])
    return r

def readLithiumResult(lithlogfn):
    with open(lithlogfn) as f:
        for line in f:
            if line.startswith("Lithium result"):
                print line.rstrip()
            if line.startswith("Lithium result: interesting"):
                return (LITH_RETESTED_STILL_INTERESTING, None)
            elif line.startswith("Lithium result: succeeded, reduced to: "):
                reducedTo = line[len("Lithium result: succeeded, reduced to: "):].rstrip() # e.g. "4 lines"
                return (LITH_FINISHED, reducedTo)
            elif line.startswith("Lithium result: not interesting") or line.startswith("Lithium result: the original testcase is not"):
                return (LITH_NO_REPRO, None)
            elif line.startswith("Lithium result: please continue using: "):
                lithiumHint = line[len("Lithium result: please continue using: "):].rstrip()
                return (LITH_PLEASE_CONTINUE, lithiumHint)
        else:
            return (LITH_BUSTED, None)

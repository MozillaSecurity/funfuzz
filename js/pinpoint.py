#!/usr/bin/env python
# coding=utf-8
# pylint: disable=invalid-name,literal-comparison,missing-docstring,too-many-arguments,too-many-branches,too-many-locals
# pylint: disable=too-many-statements
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import absolute_import, print_function

import os
import platform
import re
import shutil
import subprocess
import sys

from lithium.interestingness.utils import file_contains_str

from .jsInteresting import JS_OVERALL_MISMATCH, JS_VG_AMISS
from .inspectShell import testJsShellOrXpcshell
from ..util import fileManipulation
from ..util.lithOps import LITH_FINISHED, LITH_PLEASE_CONTINUE, runLithium
from ..util import subprocesses as sps

p0 = os.path.dirname(os.path.abspath(__file__))
autobisectpy = os.path.abspath(os.path.join(p0, os.pardir, 'autobisectjs', 'autoBisect.py'))


def pinpoint(itest, logPrefix, jsEngine, engineFlags, infilename,
             bisectRepo, buildOptionsStr, targetTime, suspiciousLevel):
    """Run Lithium and autobisect.

    itest must be an array of the form [module, ...] where module is an interestingness module.
    The module's "interesting" function must accept [...] + [jsEngine] + engineFlags + infilename
    (If it's not prepared to accept engineFlags, engineFlags must be empty.)
    """
    lithArgs = itest + [jsEngine] + engineFlags + [infilename]

    (lithResult, lithDetails) = strategicReduction(logPrefix, infilename, lithArgs, targetTime, suspiciousLevel)

    print()
    print("Done running Lithium on the part in between DDBEGIN and DDEND. To reproduce, run:")
    print(sps.shellify([sys.executable, "-u", "-m", "lithium", "--strategy=check-only"] + lithArgs))
    print()

    if bisectRepo is not "none" and targetTime >= 3 * 60 * 60 and buildOptionsStr is not None:
        if platform.uname()[2] == 'XP':
            print("Not pinpointing to exact changeset since autoBisect does not work well in WinXP.")
        elif testJsShellOrXpcshell(jsEngine) != "xpcshell":
            autobisectCmd = (
                [sys.executable, autobisectpy] +
                ["-b", buildOptionsStr] +
                ["-p", ' '.join(engineFlags + [infilename])] +
                ["-i"] + itest
            )
            print(sps.shellify(autobisectCmd))
            autoBisectLogFilename = logPrefix + "-autobisect.txt"
            subprocess.call(autobisectCmd, stdout=open(autoBisectLogFilename, "w"), stderr=subprocess.STDOUT)
            print("Done running autobisect. Log: %s" % autoBisectLogFilename)

            with open(autoBisectLogFilename, 'rb') as f:
                lines = f.readlines()
                autoBisectLog = fileManipulation.truncateMid(lines, 50, ["..."])
    else:
        autoBisectLog = []

    return (lithResult, lithDetails, autoBisectLog)


def strategicReduction(logPrefix, infilename, lithArgs, targetTime, lev):
    """Reduce jsfunfuzz output files using Lithium by using various strategies."""
    reductionCount = [0]  # This is an array because Python does not like assigning to upvars.
    backupFilename = infilename + '-backup'

    def lithReduceCmd(strategy):
        """Lithium reduction commands accepting various strategies."""
        reductionCount[0] += 1
        fullLithArgs = [x for x in (strategy + lithArgs) if x]  # Remove empty elements
        print(sps.shellify([sys.executable, "-u", "-m", "lithium"] + fullLithArgs))

        desc = '-chars' if strategy == '--char' else '-lines'
        (lithResult, lithDetails) = runLithium(
            fullLithArgs, "%s-%s%s" % (logPrefix, reductionCount[0], desc), targetTime)
        if lithResult == LITH_FINISHED:
            shutil.copy2(infilename, backupFilename)

        return lithResult, lithDetails

    print()
    print("Running the first line reduction...")
    print()
    # Step 1: Run the first instance of line reduction.
    lithResult, lithDetails = lithReduceCmd([])

    if lithDetails is not None:  # lithDetails can be None if testcase no longer becomes interesting
        origNumOfLines = int(lithDetails.split()[0])

    hasTryItOut = False
    hasTryItOutRegex = re.compile(r'count=[0-9]+; tryItOut\("')

    with open(infilename, 'rb') as f:
        for line in fileManipulation.linesWith(f, '; tryItOut("'):
            # Checks if testcase came from jsfunfuzz or compareJIT.
            # Do not use .match here, it only matches from the start of the line:
            # https://docs.python.org/2/library/re.html#search-vs-match
            hasTryItOut = hasTryItOutRegex.search(line)
            if hasTryItOut:  # Stop searching after finding the first tryItOut line.
                break

    # Step 2: Run 1 instance of 1-line reduction after moving tryItOut and count=X around.
    if lithResult == LITH_FINISHED and origNumOfLines <= 50 and hasTryItOut and lev >= JS_VG_AMISS:

        tryItOutAndCountRegex = re.compile(r'"\);\ncount=([0-9]+); tryItOut\("', re.MULTILINE)
        with open(infilename, 'rb') as f:
            infileContents = f.read()
            infileContents = re.sub(tryItOutAndCountRegex, ';\\\n"); count=\\1; tryItOut("\\\n',
                                    infileContents)
        with open(infilename, 'wb') as f:
            f.write(infileContents)

        print()
        print("Running 1 instance of 1-line reduction after moving tryItOut and count=X...")
        print()
        # --chunksize=1: Reduce only individual lines, for only 1 round.
        lithResult, lithDetails = lithReduceCmd(['--chunksize=1'])

    # Step 3: Run 1 instance of 2-line reduction after moving count=X to its own line and add a
    # 1-line offset.
    if lithResult == LITH_FINISHED and origNumOfLines <= 50 and hasTryItOut and lev >= JS_VG_AMISS:
        intendedLines = []
        with open(infilename, 'rb') as f:
            for line in f:  # The testcase is likely to already be partially reduced.
                if 'dumpln(cookie' not in line:  # jsfunfuzz-specific line ignore
                    # This should be simpler than re.compile.
                    intendedLines.append(line.replace('; count=', ';\ncount=')
                                         .replace('; tryItOut("', ';\ntryItOut("')
                                         # The 1-line offset is added here.
                                         .replace('SPLICE DDBEGIN', 'SPLICE DDBEGIN\n'))

        fileManipulation.writeLinesToFile(intendedLines, infilename)
        print()
        print("Running 1 instance of 2-line reduction after moving count=X to its own line...")
        print()
        lithResult, lithDetails = lithReduceCmd(['--chunksize=2'])

    # Step 4: Run 1 instance of 2-line reduction again, e.g. to remove pairs of STRICT_MODE lines.
    if lithResult == LITH_FINISHED and origNumOfLines <= 50 and hasTryItOut and lev >= JS_VG_AMISS:
        print()
        print("Running 1 instance of 2-line reduction again...")
        print()
        lithResult, lithDetails = lithReduceCmd(['--chunksize=2'])

    isLevOverallMismatchAsmJsAvailable = (lev == JS_OVERALL_MISMATCH) and \
        file_contains_str(infilename, 'isAsmJSCompilationAvailable')
    # Step 5 (not always run): Run character reduction within interesting lines.
    if lithResult == LITH_FINISHED and origNumOfLines <= 50 and targetTime is None and \
            lev >= JS_OVERALL_MISMATCH and not isLevOverallMismatchAsmJsAvailable:
        print()
        print("Running character reduction...")
        print()
        lithResult, lithDetails = lithReduceCmd(['--char'])

    # Step 6: Run line reduction after activating SECOND DDBEGIN with a 1-line offset.
    if lithResult == LITH_FINISHED and origNumOfLines <= 50 and hasTryItOut and lev >= JS_VG_AMISS:
        infileContents = []
        with open(infilename, 'rb') as f:
            for line in f:
                if 'NIGEBDD' in line:
                    infileContents.append(line.replace('NIGEBDD', 'DDBEGIN'))
                    infileContents.append('\n')  # The 1-line offset is added here.
                    continue
                infileContents.append(line)
        with open(infilename, 'wb') as f:
            f.writelines(infileContents)

        print()
        print("Running line reduction with a 1-line offset...")
        print()
        lithResult, lithDetails = lithReduceCmd([])

    # Step 7: Run line reduction for a final time.
    if lithResult == LITH_FINISHED and origNumOfLines <= 50 and hasTryItOut and lev >= JS_VG_AMISS:
        print()
        print("Running the final line reduction...")
        print()
        lithResult, lithDetails = lithReduceCmd([])

    # Restore from backup if testcase can no longer be reproduced halfway through reduction.
    if lithResult != LITH_FINISHED and lithResult != LITH_PLEASE_CONTINUE:
        # Probably can move instead of copy the backup, once this has stabilised.
        if os.path.isfile(backupFilename):
            shutil.copy2(backupFilename, infilename)
        else:
            print("DEBUG! backupFilename is supposed to be: %s" % backupFilename)

    return lithResult, lithDetails

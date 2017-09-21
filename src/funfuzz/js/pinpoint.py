# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Enables the funfuzz harness to use autobisectjs to discover the regressing changeset.
"""

from __future__ import absolute_import, print_function

import os
import platform
import re
import shutil
import subprocess
import sys

from lithium.interestingness.utils import file_contains_str

from .js_interesting import JS_OVERALL_MISMATCH, JS_VG_AMISS
from .inspect_shell import testJsShellOrXpcshell
from ..util import file_manipulation
from ..util.lithium_helpers import LITH_FINISHED, LITH_PLEASE_CONTINUE, runLithium
from ..util import subprocesses as sps


def pinpoint(itest, logPrefix, jsEngine, engineFlags, infilename,  # pylint: disable=invalid-name,missing-param-doc
             bisectRepo, build_options_str, targetTime, suspiciousLevel):
    # pylint: disable=missing-return-doc,missing-return-type-doc,missing-type-doc,too-many-arguments,too-many-locals
    """Run Lithium and autobisect.

    itest must be an array of the form [module, ...] where module is an interestingness module.
    The module's "interesting" function must accept [...] + [jsEngine] + engineFlags + infilename
    (If it's not prepared to accept engineFlags, engineFlags must be empty.)
    """
    lithArgs = itest + [jsEngine] + engineFlags + [infilename]  # pylint: disable=invalid-name

    (lithResult, lithDetails) = strategicReduction(  # pylint: disable=invalid-name
        logPrefix, infilename, lithArgs, targetTime, suspiciousLevel)

    print()
    print("Done running Lithium on the part in between DDBEGIN and DDEND. To reproduce, run:")
    print(sps.shellify([sys.executable, "-u", "-m", "lithium", "--strategy=check-only"] + lithArgs))
    print()

    # pylint: disable=literal-comparison
    if bisectRepo is not "none" and targetTime >= 3 * 60 * 60 and build_options_str is not None:
        if platform.uname()[2] == 'XP':
            print("Not pinpointing to exact changeset since autoBisect does not work well in WinXP.")
        elif testJsShellOrXpcshell(jsEngine) != "xpcshell":
            autobisectCmd = (  # pylint: disable=invalid-name
                [sys.executable, "-u", "-m", "funfuzz.autobisectjs"] +
                ["-b", build_options_str] +
                ["-p", ' '.join(engineFlags + [infilename])] +
                ["-i"] + itest
            )
            print(sps.shellify(autobisectCmd))
            autoBisectLogFilename = logPrefix + "-autobisect.txt"  # pylint: disable=invalid-name
            subprocess.call(autobisectCmd, stdout=open(autoBisectLogFilename, "w"), stderr=subprocess.STDOUT)
            print("Done running autobisect. Log: %s" % autoBisectLogFilename)

            with open(autoBisectLogFilename, 'rb') as f:
                lines = f.readlines()
                autoBisectLog = file_manipulation.truncateMid(lines, 50, ["..."])  # pylint: disable=invalid-name
    else:
        autoBisectLog = []  # pylint: disable=invalid-name

    return (lithResult, lithDetails, autoBisectLog)


def strategicReduction(logPrefix, infilename, lithArgs, targetTime, lev):  # pylint: disable=invalid-name
    # pylint: disable=missing-param-doc,missing-return-doc,missing-return-type-doc,missing-type-doc,too-complex
    # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    """Reduce jsfunfuzz output files using Lithium by using various strategies."""
    # This is an array because Python does not like assigning to upvars.
    reductionCount = [0]  # pylint: disable=invalid-name
    backupFilename = infilename + '-backup'  # pylint: disable=invalid-name

    def lithReduceCmd(strategy):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
        # pylint: disable=missing-return-type-doc,missing-type-doc
        """Lithium reduction commands accepting various strategies."""
        reductionCount[0] += 1
        # Remove empty elements
        fullLithArgs = [x for x in (strategy + lithArgs) if x]  # pylint: disable=invalid-name
        print(sps.shellify([sys.executable, "-u", "-m", "lithium"] + fullLithArgs))

        desc = '-chars' if strategy == '--char' else '-lines'
        (lithResult, lithDetails) = runLithium(  # pylint: disable=invalid-name
            fullLithArgs, "%s-%s%s" % (logPrefix, reductionCount[0], desc), targetTime)
        if lithResult == LITH_FINISHED:
            shutil.copy2(infilename, backupFilename)

        return lithResult, lithDetails

    print()
    print("Running the first line reduction...")
    print()
    # Step 1: Run the first instance of line reduction.
    lithResult, lithDetails = lithReduceCmd([])  # pylint: disable=invalid-name

    if lithDetails is not None:  # lithDetails can be None if testcase no longer becomes interesting
        origNumOfLines = int(lithDetails.split()[0])  # pylint: disable=invalid-name

    hasTryItOut = False  # pylint: disable=invalid-name
    hasTryItOutRegex = re.compile(r'count=[0-9]+; tryItOut\("')  # pylint: disable=invalid-name

    with open(infilename, 'rb') as f:
        for line in file_manipulation.linesWith(f, '; tryItOut("'):
            # Checks if testcase came from jsfunfuzz or compare_jit.
            # Do not use .match here, it only matches from the start of the line:
            # https://docs.python.org/2/library/re.html#search-vs-match
            hasTryItOut = hasTryItOutRegex.search(line)  # pylint: disable=invalid-name
            if hasTryItOut:  # Stop searching after finding the first tryItOut line.
                break

    # Step 2: Run 1 instance of 1-line reduction after moving tryItOut and count=X around.
    if lithResult == LITH_FINISHED and origNumOfLines <= 50 and hasTryItOut and lev >= JS_VG_AMISS:

        tryItOutAndCountRegex = re.compile(r'"\);\ncount=([0-9]+); tryItOut\("',  # pylint: disable=invalid-name
                                           re.MULTILINE)
        with open(infilename, 'rb') as f:
            infileContents = f.read()  # pylint: disable=invalid-name
            infileContents = re.sub(tryItOutAndCountRegex,  # pylint: disable=invalid-name
                                    ';\\\n"); count=\\1; tryItOut("\\\n',
                                    infileContents)
        with open(infilename, 'wb') as f:
            f.write(infileContents)

        print()
        print("Running 1 instance of 1-line reduction after moving tryItOut and count=X...")
        print()
        # --chunksize=1: Reduce only individual lines, for only 1 round.
        lithResult, lithDetails = lithReduceCmd(['--chunksize=1'])  # pylint: disable=invalid-name

    # Step 3: Run 1 instance of 2-line reduction after moving count=X to its own line and add a
    # 1-line offset.
    if lithResult == LITH_FINISHED and origNumOfLines <= 50 and hasTryItOut and lev >= JS_VG_AMISS:
        intendedLines = []  # pylint: disable=invalid-name
        with open(infilename, 'rb') as f:
            for line in f:  # The testcase is likely to already be partially reduced.
                if 'dumpln(cookie' not in line:  # jsfunfuzz-specific line ignore
                    # This should be simpler than re.compile.
                    intendedLines.append(line.replace('; count=', ';\ncount=')
                                         .replace('; tryItOut("', ';\ntryItOut("')
                                         # The 1-line offset is added here.
                                         .replace('SPLICE DDBEGIN', 'SPLICE DDBEGIN\n'))

        file_manipulation.writeLinesToFile(intendedLines, infilename)
        print()
        print("Running 1 instance of 2-line reduction after moving count=X to its own line...")
        print()
        lithResult, lithDetails = lithReduceCmd(['--chunksize=2'])  # pylint: disable=invalid-name

    # Step 4: Run 1 instance of 2-line reduction again, e.g. to remove pairs of STRICT_MODE lines.
    if lithResult == LITH_FINISHED and origNumOfLines <= 50 and hasTryItOut and lev >= JS_VG_AMISS:
        print()
        print("Running 1 instance of 2-line reduction again...")
        print()
        lithResult, lithDetails = lithReduceCmd(['--chunksize=2'])  # pylint: disable=invalid-name

    isLevOverallMismatchAsmJsAvailable = (lev == JS_OVERALL_MISMATCH and  # pylint: disable=invalid-name
                                          file_contains_str(infilename, 'isAsmJSCompilationAvailable'))
    # Step 5 (not always run): Run character reduction within interesting lines.
    if lithResult == LITH_FINISHED and origNumOfLines <= 50 and targetTime is None and \
            lev >= JS_OVERALL_MISMATCH and not isLevOverallMismatchAsmJsAvailable:
        print()
        print("Running character reduction...")
        print()
        lithResult, lithDetails = lithReduceCmd(['--char'])  # pylint: disable=invalid-name

    # Step 6: Run line reduction after activating SECOND DDBEGIN with a 1-line offset.
    if lithResult == LITH_FINISHED and origNumOfLines <= 50 and hasTryItOut and lev >= JS_VG_AMISS:
        infileContents = []  # pylint: disable=invalid-name
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
        lithResult, lithDetails = lithReduceCmd([])  # pylint: disable=invalid-name

    # Step 7: Run line reduction for a final time.
    if lithResult == LITH_FINISHED and origNumOfLines <= 50 and hasTryItOut and lev >= JS_VG_AMISS:
        print()
        print("Running the final line reduction...")
        print()
        lithResult, lithDetails = lithReduceCmd([])  # pylint: disable=invalid-name

    # Restore from backup if testcase can no longer be reproduced halfway through reduction.
    if lithResult != LITH_FINISHED and lithResult != LITH_PLEASE_CONTINUE:
        # Probably can move instead of copy the backup, once this has stabilised.
        if os.path.isfile(backupFilename):
            shutil.copy2(backupFilename, infilename)
        else:
            print("DEBUG! backupFilename is supposed to be: %s" % backupFilename)

    return lithResult, lithDetails

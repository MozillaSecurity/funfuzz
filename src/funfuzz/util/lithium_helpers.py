# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Helper functions to use the Lithium reducer.
"""

from __future__ import absolute_import, print_function

import os
import re
import shutil
import subprocess
import sys
import tempfile

from lithium.interestingness.utils import file_contains_str
from past.builtins import range  # pylint: disable=redefined-builtin

from ..js.js_interesting import JS_OVERALL_MISMATCH, JS_VG_AMISS
from ..js.inspect_shell import testJsShellOrXpcshell
from . import file_manipulation
from . import subprocesses as sps

runlithiumpy = [sys.executable, "-u", "-m", "lithium"]  # pylint: disable=invalid-name

# Status returns for runLithium and many_timed_runs
(HAPPY, NO_REPRO_AT_ALL, NO_REPRO_EXCEPT_BY_URL, LITH_NO_REPRO,
 LITH_FINISHED, LITH_RETESTED_STILL_INTERESTING, LITH_PLEASE_CONTINUE, LITH_BUSTED) = range(8)


def pinpoint(itest, logPrefix, jsEngine, engineFlags, infilename,  # pylint: disable=invalid-name,missing-param-doc
             bisectRepo, build_options_str, targetTime, suspiciousLevel):
    # pylint: disable=missing-return-doc,missing-return-type-doc,missing-type-doc,too-many-arguments,too-many-locals
    """Run Lithium and autobisectjs.

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
    if (bisectRepo is not "none" and targetTime >= 3 * 60 * 60 and
            build_options_str is not None and testJsShellOrXpcshell(jsEngine) != "xpcshell"):
        autobisectCmd = (  # pylint: disable=invalid-name
            [sys.executable, "-u", "-m", "funfuzz.autobisectjs"] +
            ["-b", build_options_str] +
            ["-p", ' '.join(engineFlags + [infilename])] +
            ["-i"] + itest
        )
        print(sps.shellify(autobisectCmd))
        autoBisectLogFilename = logPrefix + "-autobisect.txt"  # pylint: disable=invalid-name
        subprocess.call(autobisectCmd, stdout=open(autoBisectLogFilename, "w"), stderr=subprocess.STDOUT)
        print("Done running autobisectjs. Log: %s" % autoBisectLogFilename)

        with open(autoBisectLogFilename, 'r') as f:
            lines = f.readlines()
            autoBisectLog = file_manipulation.truncateMid(lines, 50, ["..."])  # pylint: disable=invalid-name
    else:
        autoBisectLog = []  # pylint: disable=invalid-name

    return (lithResult, lithDetails, autoBisectLog)


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

    with open(infilename, 'r') as f:
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
        with open(infilename, 'r') as f:
            infileContents = f.read()  # pylint: disable=invalid-name
            infileContents = re.sub(tryItOutAndCountRegex,  # pylint: disable=invalid-name
                                    ';\\\n"); count=\\1; tryItOut("\\\n',
                                    infileContents)
        with open(infilename, 'w') as f:
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
        with open(infilename, 'r') as f:
            for line in f:  # The testcase is likely to already be partially reduced.
                if 'dumpln(cookie' not in line:  # jsfunfuzz-specific line ignore
                    # This should be simpler than re.compile.
                    intendedLines.append(line.replace('; count=', ';\ncount=')
                                         .replace('; tryItOut("', ';\ntryItOut("')
                                         # The 1-line offset is added here.
                                         .replace('SPLICE DDBEGIN', 'SPLICE DDBEGIN\n'))

        with open(infilename, "w") as f:
            f.writelines(intendedLines)
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
        with open(infilename, 'r') as f:
            for line in f:
                if 'NIGEBDD' in line:
                    infileContents.append(line.replace('NIGEBDD', 'DDBEGIN'))
                    infileContents.append('\n')  # The 1-line offset is added here.
                    continue
                infileContents.append(line)
        with open(infilename, 'w') as f:
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

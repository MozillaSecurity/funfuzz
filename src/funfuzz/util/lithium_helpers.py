# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Helper functions to use the Lithium reducer.
"""

import gzip
import io
from pathlib import Path
import re
from shlex import quote
import shutil
import subprocess
import sys
import tempfile

from lithium.interestingness.utils import file_contains_str

from . import file_manipulation
from ..js.inspect_shell import testJsShellOrXpcshell
from ..js.js_interesting import JS_OVERALL_MISMATCH
from ..js.js_interesting import JS_VG_AMISS

runlithiumpy = [sys.executable, "-u", "-m", "lithium"]  # pylint: disable=invalid-name

# Status returns for runLithium and many_timed_runs
(HAPPY, LITH_NO_REPRO, LITH_FINISHED, LITH_RETESTED_STILL_INTERESTING, LITH_BUSTED) = range(5)


def pinpoint(itest, logPrefix, jsEngine, engineFlags, infilename,  # pylint: disable=invalid-name,missing-param-doc
             bisectRepo, build_options_str, targetTime, suspiciousLevel):
    # pylint: disable=missing-return-doc,missing-return-type-doc,missing-type-doc,too-many-arguments,too-many-locals
    """Run Lithium and autobisectjs.

    itest must be an array of the form [module, ...] where module is an interestingness module.
    The module's "interesting" function must accept [...] + [jsEngine] + engineFlags + infilename
    (If it's not prepared to accept engineFlags, engineFlags must be empty.)
    """
    lithArgs = itest + [str(jsEngine)] + engineFlags + [str(infilename)]  # pylint: disable=invalid-name

    (lithResult, lithDetails) = reduction_strat(  # pylint: disable=invalid-name
        logPrefix, infilename, lithArgs, targetTime, suspiciousLevel)

    print()
    print("Done running Lithium on the part in between DDBEGIN and DDEND. To reproduce, run:")
    print(" ".join(quote(str(x)) for x in [sys.executable, "-u", "-m", "lithium", "--strategy=check-only"] + lithArgs))
    print()

    # pylint: disable=literal-comparison
    if (bisectRepo != "none" and targetTime >= 3 * 60 * 60 and
            build_options_str is not None and testJsShellOrXpcshell(jsEngine) != "xpcshell"):
        autobisectCmd = (  # pylint: disable=invalid-name
            [sys.executable, "-u", "-m", "funfuzz.autobisectjs"] +
            ["-b", build_options_str] +
            ["-p", " ".join(engineFlags + [str(infilename)])] +
            ["-i"] + [str(x) for x in itest]
        )
        print(" ".join(quote(str(x)) for x in autobisectCmd))
        autobisect_log = (logPrefix.parent / f"{logPrefix.stem}-autobisect").with_suffix(".txt")
        with io.open(str(autobisect_log), "w", encoding="utf-8", errors="replace") as f:
            subprocess.run(autobisectCmd, stderr=subprocess.STDOUT, stdout=f)
        print(f"Done running autobisectjs. Log: {autobisect_log}")

        with io.open(str(autobisect_log), "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            autobisect_log_trunc = file_manipulation.truncateMid(lines, 50, ["..."])
    else:
        autobisect_log_trunc = []

    return lithResult, lithDetails, autobisect_log_trunc


def run_lithium(lithArgs, logPrefix, targetTime):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Run Lithium as a subprocess: reduce to the smallest file that has at least the same unhappiness level.

    Returns a tuple of (lithlogfn, LITH_*, details).
    """
    deletableLithTemp = None  # pylint: disable=invalid-name
    if targetTime:
        # loop is being used by bot
        deletableLithTemp = tempfile.mkdtemp(prefix="fuzzbot-lithium")  # pylint: disable=invalid-name
        lithArgs = [f"--maxruntime={targetTime}", f"--tempdir={deletableLithTemp}"] + lithArgs
    else:
        # loop is being run standalone
        lithtmp = logPrefix.parent / f"{logPrefix.stem}-lith-tmp"
        Path.mkdir(lithtmp)
        lithArgs = [f"--tempdir={lithtmp}"] + lithArgs
    lithlogfn = (logPrefix.parent / f"{logPrefix.stem}-lith-out").with_suffix(".txt")
    print(f"Preparing to run Lithium, log file {lithlogfn}")
    print(" ".join(quote(str(x)) for x in runlithiumpy + lithArgs))
    with io.open(str(lithlogfn), "w", encoding="utf-8", errors="replace") as f:
        subprocess.run(runlithiumpy + lithArgs, stderr=subprocess.STDOUT, stdout=f)
    print("Done running Lithium")
    if deletableLithTemp:
        shutil.rmtree(deletableLithTemp)
    r = readLithiumResult(lithlogfn)  # pylint: disable=invalid-name

    with open(lithlogfn, "rb") as f_in:  # Replace the old gzip subprocess call
        with gzip.open(lithlogfn.with_suffix(".txt.gz"), "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    lithlogfn.unlink()

    return r


def readLithiumResult(lithlogfn):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    with io.open(str(lithlogfn), "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("Lithium result"):
                print(line.rstrip())
            if line.startswith("Lithium result: interesting"):  # pylint: disable=no-else-return
                return LITH_RETESTED_STILL_INTERESTING, None
            elif line.startswith("Lithium result: succeeded, reduced to: "):
                # pylint: disable=invalid-name
                reducedTo = line[len("Lithium result: succeeded, reduced to: "):].rstrip()  # e.g. "4 lines"
                return LITH_FINISHED, reducedTo
            elif (line.startswith("Lithium result: not interesting") or
                  line.startswith("Lithium result: the original testcase is not")):
                return LITH_NO_REPRO, None
        return LITH_BUSTED, None


def reduction_strat(logPrefix, infilename, lithArgs, targetTime, lev):  # pylint: disable=invalid-name
    # pylint: disable=missing-param-doc,missing-return-doc,missing-return-type-doc,missing-type-doc,too-complex
    # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    """Reduce jsfunfuzz output files using Lithium by using various strategies."""

    # This is an array because Python does not like assigning to upvars.
    reductionCount = [0]  # pylint: disable=invalid-name

    def lith_reduce(strategy):
        """Lithium reduction commands accepting various strategies.

        Args:
            strategy (str): Intended strategy to use

        Returns:
            (tuple): The finished Lithium run result and details
        """
        reductionCount[0] += 1
        # Remove empty elements
        full_lith_args = [x for x in (strategy + lithArgs) if x]
        print(" ".join(quote(str(x)) for x in [sys.executable, "-u", "-m", "lithium"] + full_lith_args))

        desc = "-chars" if strategy == "--char" else "-lines"
        (lith_result, lith_details) = run_lithium(
            full_lith_args, (logPrefix.parent / f"{logPrefix.stem}-{reductionCount[0]}{desc}"), targetTime)

        return lith_result, lith_details

    print()
    print("Running the first line reduction...")
    print()
    # Step 1: Run the first instance of line reduction.
    lith_result, lith_details = lith_reduce([])

    origNumOfLines = None  # pylint: disable=invalid-name
    if lith_details is not None:  # lith_details can be None if testcase no longer becomes interesting
        origNumOfLines = int(lith_details.split()[0])  # pylint: disable=invalid-name

    hasTryItOut = False  # pylint: disable=invalid-name
    hasTryItOutRegex = re.compile(r'count=[0-9]+; tryItOut\("')  # pylint: disable=invalid-name

    with io.open(str(infilename), "r", encoding="utf-8", errors="replace") as f:
        for line in file_manipulation.linesWith(f, '; tryItOut("'):
            # Checks if testcase came from jsfunfuzz or compare_jit.
            # Do not use .match here, it only matches from the start of the line:
            # https://docs.python.org/2/library/re.html#search-vs-match
            hasTryItOut = hasTryItOutRegex.search(line)  # pylint: disable=invalid-name
            if hasTryItOut:  # Stop searching after finding the first tryItOut line.
                break

    # Step 2: Run 1 instance of 1-line reduction after moving tryItOut and count=X around.
    if lith_result == LITH_FINISHED and origNumOfLines <= 50 and hasTryItOut and lev >= JS_VG_AMISS:

        tryItOutAndCountRegex = re.compile(r'"\);\ncount=([0-9]+); tryItOut\("',  # pylint: disable=invalid-name
                                           re.MULTILINE)
        with io.open(str(infilename), "r", encoding="utf-8", errors="replace") as f:
            infileContents = f.read()  # pylint: disable=invalid-name
            infileContents = re.sub(tryItOutAndCountRegex,  # pylint: disable=invalid-name
                                    ';\\\n"); count=\\1; tryItOut("\\\n',
                                    infileContents)
        with io.open(str(infilename), "w", encoding="utf-8", errors="replace") as f:
            f.write(infileContents)

        print()
        print("Running 1 instance of 1-line reduction after moving tryItOut and count=X...")
        print()
        # --chunksize=1: Reduce only individual lines, for only 1 round.
        lith_result, lith_details = lith_reduce(["--chunksize=1"])

    # Step 3: Run 1 instance of 2-line reduction after moving count=X to its own line and add a
    # 1-line offset.
    if lith_result == LITH_FINISHED and origNumOfLines <= 50 and hasTryItOut and lev >= JS_VG_AMISS:
        intendedLines = []  # pylint: disable=invalid-name
        with io.open(str(infilename), "r", encoding="utf-8", errors="replace") as f:
            for line in f:  # The testcase is likely to already be partially reduced.
                if "dumpln(cookie" not in line:  # jsfunfuzz-specific line ignore
                    # This should be simpler than re.compile.
                    intendedLines.append(line.replace("; count=", ";\ncount=")
                                         .replace('; tryItOut("', ';\ntryItOut("')
                                         # The 1-line offset is added here.
                                         .replace("SPLICE DDBEGIN", "SPLICE DDBEGIN\n"))

        with io.open(str(infilename), "w", encoding="utf-8", errors="replace") as f:
            f.writelines(intendedLines)
        print()
        print("Running 1 instance of 2-line reduction after moving count=X to its own line...")
        print()
        lith_result, lith_details = lith_reduce(["--chunksize=2"])

    # Step 4: Run 1 instance of 2-line reduction again, e.g. to remove pairs of STRICT_MODE lines.
    if lith_result == LITH_FINISHED and origNumOfLines <= 50 and hasTryItOut and lev >= JS_VG_AMISS:
        print()
        print("Running 1 instance of 2-line reduction again...")
        print()
        lith_result, lith_details = lith_reduce(["--chunksize=2"])

    isLevOverallMismatchAsmJsAvailable = (lev == JS_OVERALL_MISMATCH and  # pylint: disable=invalid-name
                                          file_contains_str(str(infilename), b"isAsmJSCompilationAvailable"))
    # Step 5 (not always run): Run character reduction within interesting lines.
    if lith_result == LITH_FINISHED and origNumOfLines <= 50 and targetTime is None and \
            lev >= JS_OVERALL_MISMATCH and not isLevOverallMismatchAsmJsAvailable:
        print()
        print("Running character reduction...")
        print()
        lith_result, lith_details = lith_reduce(["--char"])

    # Step 6: Run line reduction after activating SECOND DDBEGIN with a 1-line offset.
    if lith_result == LITH_FINISHED and origNumOfLines <= 50 and hasTryItOut and lev >= JS_VG_AMISS:
        infileContents = []  # pylint: disable=invalid-name
        with io.open(str(infilename), "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if "NIGEBDD" in line:
                    infileContents.append(line.replace("NIGEBDD", "DDBEGIN"))
                    infileContents.append("\n")  # The 1-line offset is added here.
                    continue
                infileContents.append(line)
        with io.open(str(infilename), "w", encoding="utf-8", errors="replace") as f:
            f.writelines(infileContents)

        print()
        print("Running line reduction with a 1-line offset...")
        print()
        lith_result, lith_details = lith_reduce([])

    # Step 7: Run line reduction for a final time.
    if lith_result == LITH_FINISHED and origNumOfLines <= 50 and hasTryItOut and lev >= JS_VG_AMISS:
        print()
        print("Running the final line reduction...")
        print()
        lith_result, lith_details = lith_reduce([])

    return lith_result, lith_details

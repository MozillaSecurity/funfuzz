# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test comparing the output of SpiderMonkey using various flags (usually JIT-related).
"""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import io
import logging
from optparse import OptionParser  # pylint: disable=deprecated-module
import os
import re
import sys

from FTB.ProgramConfiguration import ProgramConfiguration
import FTB.Signatures.CrashInfo as CrashInfo
from shellescape import quote

from . import js_interesting
from . import shell_flags
from ..util import create_collector
from ..util import lithium_helpers

if sys.version_info.major == 2:
    import backports.tempfile as tempfile  # pylint: disable=import-error,no-name-in-module
    from pathlib2 import Path  # pylint: disable=import-error
    if os.name == "posix":
        import subprocess32 as subprocess  # pylint: disable=import-error
else:
    from pathlib import Path  # pylint: disable=import-error
    import subprocess
    import tempfile

FUNFUZZ_LOG = logging.getLogger("funfuzz")
logging.basicConfig(level=logging.DEBUG)

gOptions = ""  # pylint: disable=invalid-name
lengthLimit = 1000000  # pylint: disable=invalid-name


def ignore_some_stderr(err_inp):
    """Ignores parts of a list depending on whether they are needed.

    Args:
        err_inp (list): Stderr

    Returns:
        list: Stderr with potentially some lines removed
    """
    lines = []
    for line in err_inp:
        if line.endswith("malloc: enabling scribbling to detect mods to free blocks"):
            # MallocScribble outputs a line that includes the process's pid.
            # We don't want to include that pid in the comparison!
            pass
        elif "Bailed out of parallel operation" in line:
            # This error message will only appear when threads and JITs are enabled.
            pass
        else:
            lines.append(line)
    return lines


def compare_jit(jsEngine,  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc,too-many-arguments
                flags, infilename, logPrefix, repo, build_options_str, targetTime, options):
    """For use in loop.py

    Returns:
        bool: True if any kind of bug is found, otherwise False
    """
    # pylint: disable=too-many-locals
    # If Lithium uses this as an interestingness test, logPrefix is likely not a Path object, so make it one.
    logPrefix = Path(logPrefix)
    initialdir_name = (logPrefix.parent / (logPrefix.stem + "-initial"))
    # pylint: disable=invalid-name
    cl = compareLevel(jsEngine, flags, infilename, initialdir_name, options, False, True)
    lev = cl[0]

    if lev != js_interesting.JS_FINE:
        itest = [__name__, "--flags=" + " ".join(flags),
                 "--minlevel=" + str(lev), "--timeout=" + str(options.timeout), options.knownPath]
        (lithResult, _lithDetails, autoBisectLog) = lithium_helpers.pinpoint(  # pylint: disable=invalid-name
            itest, logPrefix, jsEngine, [], infilename, repo, build_options_str, targetTime, lev)
        if lithResult == lithium_helpers.LITH_FINISHED:
            FUNFUZZ_LOG.info("Retesting %s after running Lithium:", infilename)
            finaldir_name = (logPrefix.parent / (logPrefix.stem + "-final"))
            retest_cl = compareLevel(jsEngine, flags, infilename, finaldir_name, options, True, False)
            if retest_cl[0] != js_interesting.JS_FINE:
                cl = retest_cl
                quality = 0
            else:
                quality = 6
        else:
            quality = 10
        FUNFUZZ_LOG.info("compare_jit: Uploading %s with quality %s", infilename, quality)

        metadata = {}
        if autoBisectLog:
            metadata = {"autoBisectLog": "".join(autoBisectLog)}
        options.collector.submit(cl[1], str(infilename), quality, metaData=metadata)
        return True

    return False


def compareLevel(jsEngine, flags, infilename, logPrefix, options, showDetailedDiffs, quickMode):
    # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc,too-complex
    # pylint: disable=too-many-branches,too-many-arguments,too-many-locals

    # options dict must be one we can pass to js_interesting.ShellResult
    # we also use it directly for knownPath, timeout, and collector
    # Return: (lev, crashInfo) or (js_interesting.JS_FINE, None)

    assert isinstance(infilename, Path)

    combos = shell_flags.basic_flag_sets(jsEngine)

    if quickMode:
        # Only used during initial fuzzing. Allowed to have false negatives.
        combos = [combos[0]]

    if flags:
        combos.insert(0, flags)

    commands = [[jsEngine] + combo + [str(infilename)] for combo in combos]

    r0 = None
    prefix0 = None

    for i, command in enumerate(commands):
        prefix = (logPrefix.parent / ("%s-r%s" % (logPrefix.stem, str(i))))
        command = commands[i]
        r = js_interesting.ShellResult(options, command, prefix, True)  # pylint: disable=invalid-name

        oom = js_interesting.oomed(r.err)
        r.err = ignore_some_stderr(r.err)

        if (r.return_code == 1 or r.return_code == 2) and (anyLineContains(r.out, "[[script] scriptArgs*]") or (
                anyLineContains(r.err, "[scriptfile] [scriptarg...]"))):
            FUNFUZZ_LOG.info("Got usage error from:")
            FUNFUZZ_LOG.info("  %s", " ".join(quote(str(x)) for x in command))
            assert i
            js_interesting.deleteLogs(prefix)
        elif r.lev > js_interesting.JS_OVERALL_MISMATCH:
            # would be more efficient to run lithium on one or the other, but meh
            FUNFUZZ_LOG.info("%s | %s", str(infilename),
                             js_interesting.summaryString(r.issues + ["compare_jit found a more serious bug"],
                                                          r.lev,
                                                          r.runinfo.elapsedtime))
            summary_log = (logPrefix.parent / (logPrefix.stem + "-summary")).with_suffix(".txt")
            with io.open(str(summary_log), "w", encoding="utf-8", errors="replace") as f:
                f.write("\n".join(r.issues + [" ".join(quote(str(x)) for x in command),
                                              "compare_jit found a more serious bug"]) + "\n")
            FUNFUZZ_LOG.info("  %s", " ".join(quote(str(x)) for x in command))
            return r.lev, r.crashInfo
        elif r.lev != js_interesting.JS_FINE or r.return_code != 0:
            FUNFUZZ_LOG.info("%s | %s", str(infilename), js_interesting.summaryString(
                r.issues + ["compare_jit is not comparing output, because the shell exited strangely"],
                r.lev, r.runinfo.elapsedtime))
            FUNFUZZ_LOG.info("  %s", " ".join(quote(str(x)) for x in command))
            js_interesting.deleteLogs(prefix)
            if not i:
                return js_interesting.JS_FINE, None
        elif oom:
            # If the shell or python hit a memory limit, we consider the rest of the computation
            # "tainted" for the purpose of correctness comparison.
            message = "compare_jit is not comparing output: OOM"
            FUNFUZZ_LOG.info("%s | %s", str(infilename), js_interesting.summaryString(
                r.issues + [message], r.lev, r.runinfo.elapsedtime))
            js_interesting.deleteLogs(prefix)
            if not i:
                return js_interesting.JS_FINE, None
        elif not i:
            # Stash output from this run (the first one), so for subsequent runs, we can compare against it.
            (r0, prefix0) = (r, prefix)  # pylint: disable=invalid-name
        else:
            # Compare the output of this run (r.out) to the output of the first run (r0.out), etc.

            def optionDisabledAsmOnOneSide():  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
                # pylint: disable=missing-return-type-doc
                asmMsg = "asm.js type error: Disabled by javascript.options.asmjs"  # pylint: disable=invalid-name
                # pylint: disable=invalid-name
                # pylint: disable=cell-var-from-loop
                optionDisabledAsm = anyLineContains(r0.err, asmMsg) or anyLineContains(r.err, asmMsg)
                # pylint: disable=invalid-name
                optionDiffers = (("--no-asmjs" in commands[0]) != ("--no-asmjs" in command))
                return optionDisabledAsm and optionDiffers

            mismatchErr = (r.err != r0.err and not optionDisabledAsmOnOneSide())  # pylint: disable=invalid-name
            mismatchOut = (r.out != r0.out)  # pylint: disable=invalid-name

            if mismatchErr or mismatchOut:
                # Generate a short summary for stdout and a long summary for a "*-summary.txt" file.
                # pylint: disable=invalid-name
                rerunCommand = " ".join(quote(str(x)) for x in [
                    "%s -m funfuzz.js.compare_jit" % re.search("python[2-3]", os.__file__).group(0),
                    "--flags=" + " ".join(flags),
                    "--timeout=" + str(options.timeout),
                    str(options.knownPath),
                    str(jsEngine),
                    str(infilename.name)])
                (summary, issues) = summarizeMismatch(mismatchErr, mismatchOut, prefix0, prefix)
                summary = ("  " + " ".join(quote(str(x)) for x in commands[0]) + "\n  " +
                           " ".join(quote(str(x)) for x in command) + "\n\n" + summary)
                summary_log = (logPrefix.parent / (logPrefix.stem + "-summary")).with_suffix(".txt")
                with io.open(str(summary_log), "w", encoding="utf-8", errors="replace") as f:
                    f.write(rerunCommand + "\n\n" + summary)
                FUNFUZZ_LOG.info("%s | %s", str(infilename), js_interesting.summaryString(
                    issues, js_interesting.JS_OVERALL_MISMATCH, r.runinfo.elapsedtime))
                if quickMode:
                    FUNFUZZ_LOG.info(rerunCommand)
                if showDetailedDiffs:
                    FUNFUZZ_LOG.info(summary)
                    FUNFUZZ_LOG.info("")
                # Create a crashInfo object with empty stdout, and stderr showing diffs
                pc = ProgramConfiguration.fromBinary(str(jsEngine))  # pylint: disable=invalid-name
                pc.addProgramArguments(flags)
                crashInfo = CrashInfo.CrashInfo.fromRawCrashData([], summary, pc)  # pylint: disable=invalid-name
                return js_interesting.JS_OVERALL_MISMATCH, crashInfo
            else:
                # output "compare_jit: match"
                js_interesting.deleteLogs(prefix)

    # All matched :)
    js_interesting.deleteLogs(prefix0)
    return js_interesting.JS_FINE, None


# pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
def summarizeMismatch(mismatchErr, mismatchOut, prefix0, prefix1):
    issues = []
    summary = ""
    if mismatchErr:
        issues.append("[Non-crash bug] Mismatch on stderr")
        summary += "[Non-crash bug] Mismatch on stderr\n"
        err0_log = (prefix0.parent / (prefix0.stem + "-err")).with_suffix(".txt")
        err1_log = (prefix1.parent / (prefix1.stem + "-err")).with_suffix(".txt")
        summary += diffFiles(err0_log, err1_log)
    if mismatchOut:
        issues.append("[Non-crash bug] Mismatch on stdout")
        summary += "[Non-crash bug] Mismatch on stdout\n"
        out0_log = (prefix0.parent / (prefix0.stem + "-out")).with_suffix(".txt")
        out1_log = (prefix1.parent / (prefix1.stem + "-out")).with_suffix(".txt")
        summary += diffFiles(out0_log, out1_log)
    return summary, issues


def diffFiles(f1, f2):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc
    """Return a command to diff two files, along with the diff output (if it's short)."""
    diffcmd = ["diff", "-u", str(f1), str(f2)]
    s = " ".join(diffcmd) + "\n\n"  # pylint: disable=invalid-name
    diff = subprocess.run(diffcmd,
                          cwd=os.getcwdu() if sys.version_info.major == 2 else os.getcwd(),  # pylint: disable=no-member
                          stdout=subprocess.PIPE,
                          timeout=99).stdout.decode("utf-8", errors="replace")
    if len(diff) < 10000:
        s += diff + "\n\n"  # pylint: disable=invalid-name
    else:
        s += diff[:10000] + "\n(truncated after 10000 bytes)... \n\n"  # pylint: disable=invalid-name
    return s


# pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
def anyLineContains(lines, needle):
    for line in lines:
        if needle in line:
            return True

    return False


def parseOptions(args):  # pylint: disable=invalid-name
    parser = OptionParser()
    parser.disable_interspersed_args()
    parser.add_option("--minlevel",
                      type="int", dest="minimumInterestingLevel",
                      default=js_interesting.JS_OVERALL_MISMATCH,
                      help="minimum js_interesting level for lithium to consider the testcase interesting")
    parser.add_option("--timeout",
                      type="int", dest="timeout",
                      default=10,
                      help="timeout in seconds")
    parser.add_option("--flags",
                      dest="flagsSpaceSep",
                      default="",
                      help="space-separated list of one set of flags")
    options, args = parser.parse_args(args)
    if len(args) != 3:
        raise Exception("Wrong number of positional arguments. Need 3 (knownPath, jsengine, infilename).")
    options.knownPath = Path(args[0]).expanduser().resolve()
    options.jsengine = Path(args[1]).expanduser().resolve()
    options.infilename = Path(args[2]).expanduser().resolve()
    options.flags = options.flagsSpaceSep.split(" ") if options.flagsSpaceSep else []
    if not options.jsengine.is_file():
        raise OSError("js shell does not exist: %s" % options.jsengine)

    # For js_interesting:
    options.valgrind = False
    options.shellIsDeterministic = True  # We shouldn't be in compare_jit with a non-deterministic build
    options.collector = create_collector.make_collector()

    return options


# For use by Lithium and autobisectjs. (autobisectjs calls init multiple times because it changes the js engine name)
def init(args):
    global gOptions  # pylint: disable=invalid-name,global-statement
    gOptions = parseOptions(args)


# FIXME: _args is unused here, we should check if it can be removed?  # pylint: disable=fixme
def interesting(_args, cwd_prefix):
    cwd_prefix = Path(cwd_prefix)  # Lithium uses this function and cwd_prefix from Lithium is not a Path
    actualLevel = compareLevel(  # pylint: disable=invalid-name
        gOptions.jsengine, gOptions.flags, gOptions.infilename, cwd_prefix, gOptions, False, False)[0]
    return actualLevel >= gOptions.minimumInterestingLevel


def main():
    options = parseOptions(sys.argv[1:])
    FUNFUZZ_LOG.info(compareLevel(
        options.jsengine, options.flags, options.infilename,  # pylint: disable=no-member
        Path(tempfile.mkdtemp("compare_jitmain")), options, True, False)[0])


if __name__ == "__main__":
    main()

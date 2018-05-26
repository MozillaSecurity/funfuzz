# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test comparing the output of SpiderMonkey using various flags (usually JIT-related).
"""

from __future__ import absolute_import, print_function  # isort:skip

from optparse import OptionParser  # pylint: disable=deprecated-module
import os
import sys

# These pylint errors exist because FuzzManager is not Python 3-compatible yet
from FTB.ProgramConfiguration import ProgramConfiguration  # pylint: disable=import-error
import FTB.Signatures.CrashInfo as CrashInfo  # pylint: disable=import-error,no-name-in-module
from past.builtins import range
from shellescape import quote

from . import js_interesting
from . import shell_flags
from ..util import create_collector
from ..util import lithium_helpers

if sys.version_info.major == 2 and os.name == "posix":
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess

if sys.version_info.major == 2:
    from pathlib2 import Path
else:
    from pathlib import Path  # pylint: disable=import-error

gOptions = ""  # pylint: disable=invalid-name
lengthLimit = 1000000  # pylint: disable=invalid-name


def ignoreSomeOfStderr(e):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    lines = []
    for line in e:
        if line.endswith("malloc: enabling scribbling to detect mods to free blocks"):
            # MallocScribble prints a line that includes the process's pid.
            # We don't want to include that pid in the comparison!
            pass
        elif "Bailed out of parallel operation" in line:
            # This error message will only appear when threads and JITs are enabled.
            pass
        else:
            lines.append(line)
    return lines


# For use by loop
# Returns True if any kind of bug is found
def compare_jit(jsEngine, flags, infilename, logPrefix, repo, build_options_str, targetTime, options):
    # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    # pylint: disable=too-many-arguments,too-many-locals

    # pylint: disable=invalid-name
    cl = compareLevel(jsEngine, flags, infilename, logPrefix + "-initial", options, False, True)
    lev = cl[0]

    if lev != js_interesting.JS_FINE:
        itest = [__name__, "--flags=" + " ".join(flags),
                 "--minlevel=" + str(lev), "--timeout=" + str(options.timeout), options.knownPath]
        (lithResult, _lithDetails, autoBisectLog) = lithium_helpers.pinpoint(  # pylint: disable=invalid-name
            itest, logPrefix, jsEngine, [], infilename, repo, build_options_str, targetTime, lev)
        if lithResult == lithium_helpers.LITH_FINISHED:
            print("Retesting %s after running Lithium:" % infilename)
            retest_cl = compareLevel(jsEngine, flags, infilename, logPrefix + "-final", options, True, False)
            if retest_cl[0] != js_interesting.JS_FINE:
                cl = retest_cl
                quality = 0
            else:
                quality = 6
        else:
            quality = 10
        print("compare_jit: Uploading %s with quality %s" % (infilename, quality))

        metadata = {}
        if autoBisectLog:
            metadata = {"autoBisectLog": "".join(autoBisectLog)}
        options.collector.submit(cl[1], infilename, quality, metaData=metadata)
        return True

    return False


def compareLevel(jsEngine, flags, infilename, logPrefix, options, showDetailedDiffs, quickMode):
    # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc,too-complex
    # pylint: disable=too-many-branches,too-many-arguments,too-many-locals

    # options dict must be one we can pass to js_interesting.ShellResult
    # we also use it directly for knownPath, timeout, and collector
    # Return: (lev, crashInfo) or (js_interesting.JS_FINE, None)

    assert isinstance(infilename, Path)  # We can remove casting Path to str after moving to Python 3.6+ completely

    combos = shell_flags.basic_flag_sets(jsEngine)

    if quickMode:
        # Only used during initial fuzzing. Allowed to have false negatives.
        combos = [combos[0]]

    if flags:
        combos.insert(0, flags)

    commands = [[jsEngine] + combo + [str(infilename)] for combo in combos]

    for i in range(0, len(commands)):
        prefix = logPrefix + "-r" + str(i)
        command = commands[i]
        r = js_interesting.ShellResult(options, command, prefix, True)  # pylint: disable=invalid-name

        oom = js_interesting.oomed(r.err)
        r.err = ignoreSomeOfStderr(r.err)

        if (r.return_code == 1 or r.return_code == 2) and (anyLineContains(r.out, "[[script] scriptArgs*]") or (
                anyLineContains(r.err, "[scriptfile] [scriptarg...]"))):
            print("Got usage error from:")
            print("  %s" % " ".join(quote(x) for x in command))
            assert i
            js_interesting.deleteLogs(prefix)
        elif r.lev > js_interesting.JS_OVERALL_MISMATCH:
            # would be more efficient to run lithium on one or the other, but meh
            print("%s | %s" % (str(infilename),
                               js_interesting.summaryString(r.issues + ["compare_jit found a more serious bug"],
                                                            r.lev,
                                                            r.runinfo.elapsedtime)))
            with open(str(logPrefix + "-summary.txt"), "w") as f:
                f.write("\n".join(r.issues + [" ".join(quote(x) for x in command),
                                              "compare_jit found a more serious bug"]) + "\n")
            print("  %s" % " ".join(quote(x) for x in command))
            return (r.lev, r.crashInfo)
        elif r.lev != js_interesting.JS_FINE or r.return_code != 0:
            print("%s | %s" % (str(infilename), js_interesting.summaryString(
                r.issues + ["compare_jit is not comparing output, because the shell exited strangely"],
                r.lev, r.runinfo.elapsedtime)))
            print("  %s" % " ".join(quote(x) for x in command))
            js_interesting.deleteLogs(prefix)
            if not i:
                return (js_interesting.JS_FINE, None)
        elif oom:
            # If the shell or python hit a memory limit, we consider the rest of the computation
            # "tainted" for the purpose of correctness comparison.
            message = "compare_jit is not comparing output: OOM"
            print("%s | %s" % (str(infilename), js_interesting.summaryString(
                r.issues + [message], r.lev, r.runinfo.elapsedtime)))
            js_interesting.deleteLogs(prefix)
            if not i:
                return (js_interesting.JS_FINE, None)
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
                rerunCommand = " ".join(quote(x) for x in ["python -m funfuzz.js.compare_jit",
                                                           "--flags=" + " ".join(flags),
                                                           "--timeout=" + str(options.timeout),
                                                           options.knownPath,
                                                           jsEngine,
                                                           str(infilename.name)])
                (summary, issues) = summarizeMismatch(mismatchErr, mismatchOut, prefix0, prefix)
                summary = ("  " + " ".join(quote(x) for x in commands[0]) + "\n  " +
                           " ".join(quote(x) for x in command) + "\n\n" + summary)
                with open(str(logPrefix + "-summary.txt"), "w") as f:
                    f.write(rerunCommand + "\n\n" + summary)
                print("%s | %s" % (str(infilename), js_interesting.summaryString(
                    issues, js_interesting.JS_OVERALL_MISMATCH, r.runinfo.elapsedtime)))
                if quickMode:
                    print(rerunCommand)
                if showDetailedDiffs:
                    print(summary)
                    print()
                # Create a crashInfo object with empty stdout, and stderr showing diffs
                pc = ProgramConfiguration.fromBinary(jsEngine)  # pylint: disable=invalid-name
                pc.addProgramArguments(flags)
                crashInfo = CrashInfo.CrashInfo.fromRawCrashData([], summary, pc)  # pylint: disable=invalid-name
                return (js_interesting.JS_OVERALL_MISMATCH, crashInfo)
            else:
                # print "compare_jit: match"
                js_interesting.deleteLogs(prefix)

    # All matched :)
    js_interesting.deleteLogs(prefix0)
    return (js_interesting.JS_FINE, None)


# pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
def summarizeMismatch(mismatchErr, mismatchOut, prefix0, prefix):
    issues = []
    summary = ""
    if mismatchErr:
        issues.append("[Non-crash bug] Mismatch on stderr")
        summary += "[Non-crash bug] Mismatch on stderr\n"
        summary += diffFiles(prefix0 + "-err.txt", prefix + "-err.txt")
    if mismatchOut:
        issues.append("[Non-crash bug] Mismatch on stdout")
        summary += "[Non-crash bug] Mismatch on stdout\n"
        summary += diffFiles(prefix0 + "-out.txt", prefix + "-out.txt")
    return (summary, issues)


def diffFiles(f1, f2):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc
    """Return a command to diff two files, along with the diff output (if it's short)."""
    diffcmd = ["diff", "-u", f1, f2]
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
    options.knownPath = Path(args[0]).resolve()
    options.jsengine = Path(args[1]).resolve()
    options.infilename = Path(args[2]).resolve()
    options.flags = options.flagsSpaceSep.split(" ") if options.flagsSpaceSep else []
    if not options.jsengine.is_file():
        raise Exception("js shell does not exist: " + options.jsengine)

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
def interesting(_args, tempPrefix):  # pylint: disable=invalid-name
    actualLevel = compareLevel(  # pylint: disable=invalid-name
        gOptions.jsengine, gOptions.flags, gOptions.infilename, tempPrefix, gOptions, False, False)[0]
    return actualLevel >= gOptions.minimumInterestingLevel


def main():
    import tempfile
    options = parseOptions(sys.argv[1:])
    print(compareLevel(
        options.jsengine, options.flags, options.infilename,  # pylint: disable=no-member
        tempfile.mkdtemp("compare_jitmain"), options, True, False)[0])


if __name__ == "__main__":
    main()

#!/usr/bin/env python
# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test comparing the output of SpiderMonkey using various flags (usually JIT-related).
"""

from __future__ import absolute_import, print_function

import os
import sys
from optparse import OptionParser  # pylint: disable=deprecated-module

# These pylint errors exist because FuzzManager is not Python 3-compatible yet
import FTB.Signatures.CrashInfo as CrashInfo  # pylint: disable=import-error,no-name-in-module
from FTB.ProgramConfiguration import ProgramConfiguration  # pylint: disable=import-error

from . import js_interesting
from . import pinpoint
from . import shellFlags
from ..util import createCollector
from ..util import lithOps
from ..util import subprocesses as sps

gOptions = ""  # pylint: disable=invalid-name
lengthLimit = 1000000  # pylint: disable=invalid-name


def lastLine(err):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    lines = err.split("\n")
    if len(lines) >= 2:
        return lines[-2]
    return ""


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


# For use by loop.py
# Returns True if any kind of bug is found
def compare_jit(jsEngine, flags, infilename, logPrefix, repo, build_options_str, targetTime, options):
    # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    # pylint: disable=too-many-arguments,too-many-locals

    # pylint: disable=invalid-name
    cl = compareLevel(jsEngine, flags, infilename, logPrefix + "-initial", options, False, True)
    lev = cl[0]

    if lev != js_interesting.JS_FINE:
        itest = [__file__, "--flags=" + ' '.join(flags),
                 "--minlevel=" + str(lev), "--timeout=" + str(options.timeout), options.knownPath]
        (lithResult, _lithDetails, autoBisectLog) = pinpoint.pinpoint(  # pylint: disable=invalid-name
            itest, logPrefix, jsEngine, [], infilename, repo, build_options_str, targetTime, lev)
        if lithResult == lithOps.LITH_FINISHED:
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
            metadata = {"autoBisectLog": ''.join(autoBisectLog)}
        options.collector.submit(cl[1], infilename, quality, metaData=metadata)
        return True

    return False


def compareLevel(jsEngine, flags, infilename, logPrefix, options, showDetailedDiffs, quickMode):
    # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc,too-complex
    # pylint: disable=too-many-branches,too-many-arguments,too-many-locals

    # options dict must be one we can pass to js_interesting.ShellResult
    # we also use it directly for knownPath, timeout, and collector
    # Return: (lev, crashInfo) or (js_interesting.JS_FINE, None)

    combos = shellFlags.basicFlagSets(jsEngine)

    if quickMode:
        # Only used during initial fuzzing. Allowed to have false negatives.
        combos = [combos[0]]

    if flags:
        combos.append(flags)

    commands = [[jsEngine] + combo + [infilename] for combo in combos]

    for i in range(0, len(commands)):
        prefix = logPrefix + "-r" + str(i)
        command = commands[i]
        r = js_interesting.ShellResult(options, command, prefix, True)  # pylint: disable=invalid-name

        oom = js_interesting.oomed(r.err)
        r.err = ignoreSomeOfStderr(r.err)

        if (r.return_code == 1 or r.return_code == 2) and (anyLineContains(r.out, '[[script] scriptArgs*]') or (
                anyLineContains(r.err, '[scriptfile] [scriptarg...]'))):
            print("Got usage error from:")
            print("  %s" % sps.shellify(command))
            assert i
            js_interesting.deleteLogs(prefix)
        elif r.lev > js_interesting.JS_OVERALL_MISMATCH:
            # would be more efficient to run lithium on one or the other, but meh
            print("%s | %s" % (infilename,
                               js_interesting.summaryString(r.issues + ["compare_jit found a more serious bug"],
                                                            r.lev,
                                                            r.runinfo.elapsedtime)))
            with open(logPrefix + "-summary.txt", 'wb') as f:
                f.write('\n'.join(r.issues + [sps.shellify(command), "compare_jit found a more serious bug"]) + '\n')
            print("  %s" % sps.shellify(command))
            return (r.lev, r.crashInfo)
        elif r.lev != js_interesting.JS_FINE or r.return_code != 0:
            print("%s | %s" % (infilename, js_interesting.summaryString(
                r.issues + ["compare_jit is not comparing output, because the shell exited strangely"],
                r.lev, r.runinfo.elapsedtime)))
            print("  %s" % sps.shellify(command))
            js_interesting.deleteLogs(prefix)
            if not i:
                return (js_interesting.JS_FINE, None)
        elif oom:
            # If the shell or python hit a memory limit, we consider the rest of the computation
            # "tainted" for the purpose of correctness comparison.
            message = "compare_jit is not comparing output: OOM"
            print("%s | %s" % (infilename, js_interesting.summaryString(
                r.issues + [message], r.lev, r.runinfo.elapsedtime)))
            js_interesting.deleteLogs(prefix)
            if not i:
                return (js_interesting.JS_FINE, None)
        elif not i:
            # Stash output from this run (the first one), so for subsequent runs, we can compare against it.
            (r0, prefix0) = (r, prefix)  # pylint: disable=invalid-name
        else:
            # Compare the output of this run (r.out) to the output of the first run (r0.out), etc.

            def fpuOptionDisabledAsmOnOneSide(fpuAsmMsg):  # pylint: disable=invalid-name,missing-docstring
                # pylint: disable=missing-return-doc,missing-return-type-doc
                # pylint: disable=invalid-name
                fpuOptionDisabledAsm = fpuAsmMsg in r0.err or fpuAsmMsg in r.err  # pylint: disable=cell-var-from-loop
                # pylint: disable=invalid-name
                # pylint: disable=cell-var-from-loop
                fpuOptionDiffers = (("--no-fpu" in commands[0]) != ("--no-fpu" in command))
                return fpuOptionDisabledAsm and fpuOptionDiffers

            def optionDisabledAsmOnOneSide():  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
                # pylint: disable=missing-return-type-doc
                asmMsg = "asm.js type error: Disabled by javascript.options.asmjs"  # pylint: disable=invalid-name
                # pylint: disable=invalid-name
                # pylint: disable=cell-var-from-loop
                optionDisabledAsm = anyLineContains(r0.err, asmMsg) or anyLineContains(r.err, asmMsg)
                # pylint: disable=invalid-name
                optionDiffers = (("--no-asmjs" in commands[0]) != ("--no-asmjs" in command))
                return optionDisabledAsm and optionDiffers

            mismatchErr = (r.err != r0.err and  # pylint: disable=invalid-name
                           # --no-fpu (on debug x86_32 only) turns off asm.js compilation, among other things.
                           # This should only affect asm.js diagnostics on stderr.
                           not fpuOptionDisabledAsmOnOneSide("asm.js type error: "
                                                             "Disabled by lack of floating point support") and
                           # And also wasm stuff. See bug 1243031.
                           not fpuOptionDisabledAsmOnOneSide("WebAssembly is not supported on the current device") and
                           not optionDisabledAsmOnOneSide())
            mismatchOut = (r.out != r0.out)  # pylint: disable=invalid-name

            if mismatchErr or mismatchOut:
                # Generate a short summary for stdout and a long summary for a "*-summary.txt" file.
                # pylint: disable=invalid-name
                rerunCommand = sps.shellify(['~/funfuzz/js/compare_jit.py', "--flags=" + ' '.join(flags),
                                             "--timeout=" + str(options.timeout), options.knownPath, jsEngine,
                                             os.path.basename(infilename)])
                (summary, issues) = summarizeMismatch(mismatchErr, mismatchOut, prefix0, prefix)
                summary = "  " + sps.shellify(commands[0]) + "\n  " + sps.shellify(command) + "\n\n" + summary
                with open(logPrefix + "-summary.txt", 'wb') as f:
                    f.write(rerunCommand + "\n\n" + summary)
                print("%s | %s" % (infilename, js_interesting.summaryString(
                    issues, js_interesting.JS_OVERALL_MISMATCH, r.runinfo.elapsedtime)))
                if quickMode:
                    print(rerunCommand)
                if showDetailedDiffs:
                    print(summary)
                    print()
                # Create a crashInfo object with empty stdout, and stderr showing diffs
                pc = ProgramConfiguration.fromBinary(jsEngine)  # pylint: disable=invalid-name
                pc.addProgramArguments(flags)  # pylint: disable=invalid-name
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
    s = ' '.join(diffcmd) + "\n\n"  # pylint: disable=invalid-name
    diff = sps.captureStdout(diffcmd, ignoreExitCode=True)[0]
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
                      help="minimum js/js_interesting.py level for lithium to consider the testcase interesting")
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
    options.knownPath = args[0]
    options.jsengine = args[1]
    options.infilename = args[2]
    options.flags = options.flagsSpaceSep.split(" ") if options.flagsSpaceSep else []
    if not os.path.exists(options.jsengine):
        raise Exception("js shell does not exist: " + options.jsengine)

    # For js_interesting:
    options.valgrind = False
    options.shellIsDeterministic = True  # We shouldn't be in compare_jit with a non-deterministic build
    options.collector = createCollector.createCollector("jsfunfuzz")

    return options


# For use by Lithium and autoBisect. (autoBisect calls init multiple times because it changes the js engine name)
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

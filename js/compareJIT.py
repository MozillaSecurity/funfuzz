#!/usr/bin/env python

import os
import pinpoint
import sys

from optparse import OptionParser

import jsInteresting
import shellFlags

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
import subprocesses as sps
import lithOps
import createCollector

# From FuzzManager (in sys.path thanks to import createCollector above)
import FTB.Signatures.CrashInfo as CrashInfo
from FTB.ProgramConfiguration import ProgramConfiguration


lengthLimit = 1000000


def lastLine(err):
    lines = err.split("\n")
    if len(lines) >= 2:
        return lines[-2]
    return ""


def ignoreSomeOfStderr(e):
    lines = []
    for line in e:
        if line.endswith("malloc: enabling scribbling to detect mods to free blocks"):
            # MallocScribble prints a line that includes the process's pid.  We don't want to include that pid in the comparison!
            pass
        elif "Bailed out of parallel operation" in line:
            # This error message will only appear when threads and JITs are enabled.
            pass
        else:
            lines.append(line)
    return lines


# For use by loopjsfunfuzz.py
# Returns True if any kind of bug is found
def compareJIT(jsEngine, flags, infilename, logPrefix, repo, buildOptionsStr, targetTime, options):
    cl = compareLevel(jsEngine, flags, infilename, logPrefix + "-initial", options, False, True)
    lev = cl[0]

    if lev != jsInteresting.JS_FINE:
        itest = [__file__, "--flags="+' '.join(flags), "--minlevel="+str(lev), "--timeout="+str(options.timeout), options.knownPath]
        (lithResult, lithDetails) = pinpoint.pinpoint(itest, logPrefix, jsEngine, [], infilename, repo, buildOptionsStr, targetTime, lev)
        if lithResult == lithOps.LITH_FINISHED:
            print "Retesting " + infilename + " after running Lithium:"
            retest_cl = compareLevel(jsEngine, flags, infilename, logPrefix + "-final", options, True, False)
            if retest_cl[0] != jsInteresting.JS_FINE:
                cl = retest_cl
                quality = 0
            else:
                quality = 6
        else:
            quality = 10
        print "compareJIT: Uploading " + infilename + " with quality " + str(quality)
        options.collector.submit(cl[1], infilename, quality)
        return True

    return False


def compareLevel(jsEngine, flags, infilename, logPrefix, options, showDetailedDiffs, quickMode):
    # options dict must be one we can pass to jsInteresting.ShellResult
    # we also use it directly for knownPath, timeout, and collector
    # Return: (lev, crashInfo) or (jsInteresting.JS_FINE, None)

    combos = shellFlags.basicFlagSets(jsEngine)

    if quickMode:
        # Only used during initial fuzzing. Allowed to have false negatives.
        combos = [combos[0]]

    if len(flags):
        combos.append(flags)

    commands = [[jsEngine] + combo + [infilename] for combo in combos]

    for i in range(0, len(commands)):
        prefix = logPrefix + "-r" + str(i)
        command = commands[i]
        r = jsInteresting.ShellResult(options, command, prefix, True)

        oom = jsInteresting.oomed(r.err)
        r.err = ignoreSomeOfStderr(r.err)

        if (r.rc == 1 or r.rc == 2) and (anyLineContains(r.out, '[[script] scriptArgs*]') or anyLineContains(r.err, '[scriptfile] [scriptarg...]')):
            print "Got usage error from:"
            print "  " + sps.shellify(command)
            assert i > 0
            jsInteresting.deleteLogs(prefix)
        elif r.lev > jsInteresting.JS_OVERALL_MISMATCH:
            # would be more efficient to run lithium on one or the other, but meh
            print infilename + " | " + jsInteresting.summaryString(r.issues + ["compareJIT found a more serious bug"], r.lev, r.runinfo.elapsedtime)
            with open(logPrefix + "-summary.txt", 'wb') as f:
                f.write('\n'.join(r.issues + [sps.shellify(command), "compareJIT found a more serious bug"]) + '\n')
            print "  " + sps.shellify(command)
            return (r.lev, r.crashInfo)
        elif r.lev != jsInteresting.JS_FINE or r.rc != 0:
            print infilename + " | " + jsInteresting.summaryString(r.issues + ["compareJIT is not comparing output, because the shell exited strangely"], r.lev, r.runinfo.elapsedtime)
            print "  " + sps.shellify(command)
            jsInteresting.deleteLogs(prefix)
            if i == 0:
                return (jsInteresting.JS_FINE, None)
        elif oom:
            # If the shell or python hit a memory limit, we consider the rest of the computation
            # "tainted" for the purpose of correctness comparison.
            message = "compareJIT is not comparing output: OOM"
            print infilename + " | " + jsInteresting.summaryString(r.issues + [message], r.lev, r.runinfo.elapsedtime)
            jsInteresting.deleteLogs(prefix)
            if i == 0:
                return (jsInteresting.JS_FINE, None)
        elif i == 0:
            # Stash output from this run (the first one), so for subsequent runs, we can compare against it.
            (r0, prefix0) = (r, prefix)
        else:
            # Compare the output of this run (r.out) to the output of the first run (r0.out), etc.

            def fpuOptionDisabledAsmOnOneSide():
                # --no-fpu (on debug x86_32 only) turns off asm.js compilation, among other things.
                # This should only affect asm.js diagnostics on stderr.
                fpuAsmMsg = "asm.js type error: Disabled by lack of floating point support"
                fpuOptionDisabledAsm = anyLineContains(r0.err, fpuAsmMsg) or anyLineContains(r.err, fpuAsmMsg)
                fpuOptionDiffers = (("--no-fpu" in commands[0]) != ("--no-fpu" in command))
                return (fpuOptionDisabledAsm and fpuOptionDiffers)

            def optionDisabledAsmOnOneSide():
                asmMsg = "asm.js type error: Disabled by javascript.options.asmjs"
                optionDisabledAsm = anyLineContains(r0.err, asmMsg) or anyLineContains(r.err, asmMsg)
                optionDiffers = (("--no-asmjs" in commands[0]) != ("--no-asmjs" in command))
                return (optionDisabledAsm and optionDiffers)

            mismatchErr = (r.err != r0.err and not fpuOptionDisabledAsmOnOneSide() and not optionDisabledAsmOnOneSide())
            mismatchOut = (r.out != r0.out)

            if mismatchErr or mismatchOut:
                # Generate a short summary for stdout and a long summary for a "*-summary.txt" file.
                rerunCommand = sps.shellify(['~/funfuzz/js/compareJIT.py', "--flags="+' '.join(flags),
                                             "--timeout="+str(options.timeout), options.knownPath, jsEngine,
                                             os.path.basename(infilename)])
                (summary, issues) = summarizeMismatch(mismatchErr, mismatchOut, prefix0, prefix)
                summary = "  " + sps.shellify(commands[0]) + "\n  " + sps.shellify(command) + "\n\n" + summary
                with open(logPrefix + "-summary.txt", 'wb') as f:
                    f.write(rerunCommand + "\n\n" + summary)
                print infilename + " | " + jsInteresting.summaryString(issues, jsInteresting.JS_OVERALL_MISMATCH, r.runinfo.elapsedtime)
                if quickMode:
                    print rerunCommand
                if showDetailedDiffs:
                    print summary
                    print ""
                # Create a crashInfo object with empty stdout, and stderr showing diffs
                pc = ProgramConfiguration.fromBinary(jsEngine)
                pc.addProgramArguments(flags)
                crashInfo = CrashInfo.CrashInfo.fromRawCrashData([], summary, pc)
                return (jsInteresting.JS_OVERALL_MISMATCH, crashInfo)
            else:
                #print "compareJIT: match"
                jsInteresting.deleteLogs(prefix)

    # All matched :)
    jsInteresting.deleteLogs(prefix0)
    return (jsInteresting.JS_FINE, None)


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


def diffFiles(f1, f2):
    '''Return a command to diff two files, along with the diff output (if it's short)'''
    diffcmd = ["diff", "-u", f1, f2]
    s = ' '.join(diffcmd) + "\n\n"
    diff = sps.captureStdout(diffcmd, ignoreExitCode=True)[0]
    if len(diff) < 10000:
        s += diff + "\n\n"
    else:
        s += diff[:10000] + "\n(truncated after 10000 bytes)... \n\n"
    return s


def anyLineContains(lines, needle):
    for line in lines:
        if needle in line:
            return True

    return False


def parseOptions(args):
    parser = OptionParser()
    parser.disable_interspersed_args()
    parser.add_option("--minlevel",
                      type="int", dest="minimumInterestingLevel",
                      default=jsInteresting.JS_OVERALL_MISMATCH,
                      help="minimum js/jsInteresting.py level for lithium to consider the testcase interesting")
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

    # For jsInteresting:
    options.valgrind = False
    options.shellIsDeterministic = True  # We shouldn't be in compareJIT with a non-deterministic build
    options.collector = createCollector.createCollector("jsfunfuzz")

    return options


# For use by Lithium and autoBisect. (autoBisect calls init multiple times because it changes the js engine name)
def init(args):
    global gOptions
    gOptions = parseOptions(args)
def interesting(args, tempPrefix):
    actualLevel = compareLevel(gOptions.jsengine, gOptions.flags, gOptions.infilename, tempPrefix, gOptions, False, False)[0]
    return actualLevel >= gOptions.minimumInterestingLevel


def main():
    import tempfile
    options = parseOptions(sys.argv[1:])
    print compareLevel(options.jsengine, options.flags, options.infilename, tempfile.mkdtemp("compareJITmain"), options, True, False)[0]
if __name__ == "__main__":
    main()

#!/usr/bin/env python

import os
import pinpoint
import subprocess
import sys

from optparse import OptionParser

import jsInteresting
import shellFlags

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
import subprocesses as sps
import lithOps


lengthLimit = 1000000

def lastLine(err):
    lines = err.split("\n")
    if len(lines) >= 2:
        return lines[-2]
    return ""


def ignoreSomeOfStderr(e):
    rawlines = e.split("\n")
    lines = []
    for line in rawlines:
        if line.endswith("malloc: enabling scribbling to detect mods to free blocks"):
            # MallocScribble prints a line that includes the process's pid.  We don't want to include that pid in the comparison!
            pass
        elif "Bailed out of parallel operation" in line:
            # This error message will only appear when threads and JITs are enabled.
            pass
        else:
            lines.append(line)
    return "\n".join(lines)

# For use by loopjsfunfuzz.py
def compareJIT(jsEngine, flags, infilename, logPrefix, knownPath, repo, buildOptionsStr, timeout, targetTime):
    lev = compareLevel(jsEngine, flags, infilename, logPrefix + "-initial", knownPath, timeout, False, True)

    if lev != jsInteresting.JS_FINE:
        itest = [__file__, "--flags="+' '.join(flags), "--minlevel="+str(lev), "--timeout="+str(timeout), knownPath]
        (lithResult, lithDetails) = pinpoint.pinpoint(itest, logPrefix, jsEngine, [], infilename, repo, buildOptionsStr, targetTime, lev)
        print "Retesting " + infilename + " after running Lithium:"
        print compareLevel(jsEngine, flags, infilename, logPrefix + "-final", knownPath, timeout, True, False)
        return (lithResult, lithDetails)
    else:
        return (lithOps.HAPPY, None)


def compareLevel(jsEngine, flags, infilename, logPrefix, knownPath, timeout, showDetailedDiffs, quickMode):
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
        (lev, issues, r) = jsInteresting.baseLevel(command, timeout, knownPath, prefix)

        with open(prefix + "-out.txt") as f:
            r.out = f.read(lengthLimit)
        with open(prefix + "-err.txt") as f:
            r.err = f.read(lengthLimit)

        oom = jsInteresting.hitMemoryLimit(r.err)
        if (not oom) and (len(r.err) + 5 > lengthLimit):
            # The output was too long for Python to read it in all at once. Assume the worst.
            oom = "stderr too long"

        r.err = ignoreSomeOfStderr(r.err)

        if (r.rc == 1 or r.rc == 2) and (r.out.find('[[script] scriptArgs*]') != -1 or r.err.find('[scriptfile] [scriptarg...]') != -1):
            print "Got usage error from:"
            print "  " + sps.shellify(command)
            assert i > 0
            jsInteresting.deleteLogs(prefix)
        elif lev > jsInteresting.JS_OVERALL_MISMATCH:
            # would be more efficient to run lithium on one or the other, but meh
            print infilename + " | " + jsInteresting.summaryString(issues + ["compareJIT found a more serious bug"], lev, r.elapsedtime)
            with open(logPrefix + "-summary.txt", 'wb') as f:
                f.write('\n'.join(issues + [sps.shellify(command), "compareJIT found a more serious bug"]))
            print "  " + sps.shellify(command)
            return lev
        elif lev != jsInteresting.JS_FINE:
            print infilename + " | " + jsInteresting.summaryString(issues + ["compareJIT is not comparing output, because the shell exited strangely"], lev, r.elapsedtime)
            print "  " + sps.shellify(command)
            jsInteresting.deleteLogs(prefix)
            if i == 0:
                return jsInteresting.JS_FINE
        elif oom:
            # If the shell or python hit a memory limit, we consider the rest of the computation
            # "tainted" for the purpose of correctness comparison.
            message = "compareJIT is not comparing output: OOM (" + oom + ")"
            print infilename + " | " + jsInteresting.summaryString(issues + [message], lev, r.elapsedtime)
            jsInteresting.deleteLogs(prefix)
            if i == 0:
                return jsInteresting.JS_FINE
        elif i == 0:
            # Stash output from this run (the first one), so for subsequent runs, we can compare against it.
            (r0, prefix0) = (r, prefix)
        else:
            # Compare the output of this run (r.out) to the output of the first run (r0.out), etc.

            def fpuOptionDisabledAsmOnOneSide():
                # --no-fpu (on debug x86_32 only) turns off asm.js compilation, among other things.
                # This should only affect asm.js diagnostics on stderr.
                fpuAsmMsg = "asm.js type error: Disabled by lack of floating point support"
                fpuOptionDisabledAsm = fpuAsmMsg in r0.err or fpuAsmMsg in r.err
                fpuOptionDiffers = (("--no-fpu" in commands[0]) != ("--no-fpu" in command))
                return (fpuOptionDisabledAsm and fpuOptionDiffers)

            def optionDisabledAsmOnOneSide():
                asmMsg = "asm.js type error: Disabled by javascript.options.asmjs"
                optionDisabledAsm = asmMsg in r0.err or asmMsg in r.err
                optionDiffers = (("--no-asmjs" in commands[0]) != ("--no-asmjs" in command))
                return (optionDisabledAsm and optionDiffers)

            mismatchErr = (r.err != r0.err and not fpuOptionDisabledAsmOnOneSide() and not optionDisabledAsmOnOneSide())
            mismatchOut = (r.out != r0.out)

            if mismatchErr or mismatchOut:
                # Generate a short summary for stdout and a long summary for a "*-summary.txt" file.
                rerunCommand = sps.shellify(['~/fuzzing/js/compareJIT.py', "--flags="+' '.join(flags),
                                             "--timeout="+str(timeout), knownPath, jsEngine,
                                             os.path.basename(infilename)])
                (summary, issues) = summarizeMismatch(mismatchErr, mismatchOut, prefix0, prefix)
                summary = "  " + sps.shellify(commands[0]) + "\n  " + sps.shellify(command) + "\n\n" + summary
                with open(logPrefix + "-summary.txt", 'wb') as f:
                    f.write(rerunCommand + "\n\n" + summary)
                print infilename + " | " + jsInteresting.summaryString(issues, jsInteresting.JS_OVERALL_MISMATCH, r.elapsedtime)
                if quickMode:
                    print rerunCommand
                if showDetailedDiffs:
                    print summary
                    print ""
                return jsInteresting.JS_OVERALL_MISMATCH
            else:
                #print "compareJIT: match"
                jsInteresting.deleteLogs(prefix)

    # All matched :)
    jsInteresting.deleteLogs(prefix0)
    return jsInteresting.JS_FINE

def summarizeMismatch(mismatchErr, mismatchOut, prefix0, prefix):
    issues = []
    summary = ""
    if mismatchErr:
        issues.append("Mismatch on stderr")
        summary += diffFiles(prefix0 + "-err.txt", prefix + "-err.txt")
    if mismatchOut:
        issues.append("Mismatch on stdout")
        summary += diffFiles(prefix0 + "-out.txt", prefix + "-out.txt")
    return (summary, issues)


def diffFiles(f1, f2):
    '''Return a command to diff two files, along with the diff output (if it's short)'''
    diffcmd = ["diff", "-u", f1, f2]
    s = ' '.join(diffcmd) + "\n\n"
    diff = sps.captureStdout(diffcmd, ignoreExitCode=True)[0]
    if len(diff) < 10000:
        s += diff + "\n\n"
    return s


def parseOptions(args):
    parser = OptionParser()
    parser.disable_interspersed_args()
    parser.add_option("--minlevel",
                      type = "int", dest = "minimumInterestingLevel",
                      default = jsInteresting.JS_OVERALL_MISMATCH,
                      help = "minimum js/jsInteresting.py level for lithium to consider the testcase interesting")
    parser.add_option("--timeout",
                      type = "int", dest = "timeout",
                      default = 10,
                      help = "timeout in seconds")
    parser.add_option("--flags",
                      dest = "flagsSpaceSep",
                      default = "",
                      help = "space-separated list of one set of flags")
    options, args = parser.parse_args(args)
    if len(args) != 3:
        raise Exception("Wrong number of positional arguments. Need 3 (knownPath, jsengine, infilename).")
    options.knownPath = args[0]
    options.jsengine = args[1]
    options.infilename = args[2]
    options.flags = options.flagsSpaceSep.split(" ") if options.flagsSpaceSep else []
    if not os.path.exists(options.jsengine):
        raise Exception("js shell does not exist: " + options.jsengine)
    return options

# For use by Lithium and autoBisect. (autoBisect calls init multiple times because it changes the js engine name)
def init(args):
    global gOptions
    gOptions = parseOptions(args)
def interesting(args, tempPrefix):
    actualLevel = compareLevel(gOptions.jsengine, gOptions.flags, gOptions.infilename, tempPrefix, gOptions.knownPath, gOptions.timeout, False, False)
    return actualLevel >= gOptions.minimumInterestingLevel

def main():
    import tempfile
    options = parseOptions(sys.argv[1:])
    print compareLevel(options.jsengine, options.flags, options.infilename, tempfile.mkdtemp("compareJITmain"), options.knownPath, options.timeout, True, False)
if __name__ == "__main__":
    main()

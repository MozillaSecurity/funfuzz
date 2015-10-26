#!/usr/bin/env python

import os
import sys

from optparse import OptionParser

import inspectShell
p0 = os.path.dirname(os.path.abspath(__file__))
p1 = os.path.abspath(os.path.join(p0, os.pardir, os.pardir, 'lithium', 'interestingness'))
sys.path.append(p1)
import timedRun
p2 = os.path.abspath(os.path.join(p0, os.pardir, "detect"))
sys.path.append(p2)
import detect_malloc_errors
import findIgnoreLists
p3 = os.path.abspath(os.path.join(p0, os.pardir, 'util'))
sys.path.append(p3)
import subprocesses as sps
import createCollector
import fileManipulation

# From FuzzManager (in sys.path thanks to import createCollector above)
import FTB.Signatures.CrashInfo as CrashInfo


# Levels of unhappiness.
# These are in order from "most expected to least expected" rather than "most ok to worst".
# Fuzzing will note the level, and pass it to Lithium.
# Lithium is allowed to go to a higher level.
JS_LEVELS = 7
JS_LEVEL_NAMES = [
    "fine",
    "jsfunfuzz did not finish",
    "jsfunfuzz decided to exit",
    "overall mismatch",
    "valgrind error",
    "malloc error",
    "new assert or crash"
]
assert len(JS_LEVEL_NAMES) == JS_LEVELS
(
    JS_FINE,
    JS_DID_NOT_FINISH,                  # correctness (only jsfunfuzzLevel)
    JS_DECIDED_TO_EXIT,                 # correctness (only jsfunfuzzLevel)
    JS_OVERALL_MISMATCH,                # correctness (only compareJIT)
    JS_VG_AMISS,                        # memory safety
    JS_MALLOC_ERROR,                    # memory safety
    JS_NEW_ASSERT_OR_CRASH              # memory safety or other issue that is definitely a bug
) = range(JS_LEVELS)


VALGRIND_ERROR_EXIT_CODE = 77


class ShellResult:

    # options dict should include: timeout, knownPath, collector, valgrind, shellIsDeterministic
    def __init__(self, options, runthis, logPrefix, inCompareJIT):
        # This relies on the shell being a local one from compileShell.py:
        pc = createCollector.ProgramConfiguration.fromBinary(runthis[0])
        pc.addProgramArguments(runthis[1:])

        if options.valgrind:
            runthis = (
                inspectShell.constructVgCmdList(errorCode=VALGRIND_ERROR_EXIT_CODE) +
                valgrindSuppressions(options.knownPath) +
                runthis)

        preexec_fn = ulimitSet if os.name == 'posix' else None
        runinfo = timedRun.timed_run(runthis, options.timeout, logPrefix, preexec_fn=preexec_fn)

        lev = JS_FINE
        issues = []
        auxCrashData = []

        # FuzzManager expects a list of strings rather than an iterable, so bite the
        # bullet and 'readlines' everything into memory.
        with open(logPrefix + "-out.txt") as f:
            out = f.readlines()
        with open(logPrefix + "-err.txt") as f:
            err = f.readlines()

        if options.valgrind and runinfo.rc == VALGRIND_ERROR_EXIT_CODE:
            issues.append("valgrind reported an error")
            lev = max(lev, JS_VG_AMISS)
            valgrindErrorPrefix = "==" + str(runinfo.pid) + "=="
            for line in err:
                if valgrindErrorPrefix and line.startswith(valgrindErrorPrefix):
                    issues.append(line.rstrip())
        elif runinfo.sta == timedRun.CRASHED:
            sps.grabCrashLog(runthis[0], runinfo.pid, logPrefix, True)
            with open(logPrefix + "-crash.txt") as f:
                auxCrashData = f.readlines()
        elif detect_malloc_errors.amiss(logPrefix):
            issues.append("malloc error")
            lev = max(lev, JS_MALLOC_ERROR)
        elif runinfo.rc == 0 and not inCompareJIT:
            # We might have(??) run jsfunfuzz directly, so check for special kinds of bugs
            for line in out:
                if line.startswith("Found a bug: ") and not ("NestTest" in line and oomed(err)):
                    lev = JS_DECIDED_TO_EXIT
                    issues.append(line.rstrip())
            if options.shellIsDeterministic and not understoodJsfunfuzzExit(out, err) and not oomed(err):
                issues.append("jsfunfuzz didn't finish")
                lev = JS_DID_NOT_FINISH

        # Copy non-crash issues to where FuzzManager's "AssertionHelper.py" can see it.
        if lev != JS_FINE:
            for issue in issues:
                err.append("[jsInteresting.py] " + issue)

        # Finally, make a CrashInfo object and parse stack traces for asan/crash/assertion bugs
        crashInfo = CrashInfo.CrashInfo.fromRawCrashData(out, err, pc, auxCrashData=auxCrashData)

        createCollector.printCrashInfo(crashInfo)
        if not isinstance(crashInfo, CrashInfo.NoCrashInfo):
            lev = max(lev, JS_NEW_ASSERT_OR_CRASH)

        match = options.collector.search(crashInfo)
        if match[0] is not None:
            createCollector.printMatchingSignature(match)
            lev = JS_FINE

        print logPrefix + " | " + summaryString(issues, lev, runinfo.elapsedtime)

        if lev != JS_FINE:
            fileManipulation.writeLinesToFile(
                ['Number: ' + logPrefix + '\n',
                 'Command: ' + sps.shellify(options.jsengineWithArgs) + '\n'] +
                ['Status: ' + i + "\n" for i in issues],
                logPrefix + '-summary.txt')

        self.lev = lev
        self.out = out
        self.err = err
        self.issues = issues
        self.crashInfo = crashInfo
        self.match = match
        self.runinfo = runinfo
        self.rc = runinfo.rc


def understoodJsfunfuzzExit(out, err):
    for line in err:
        if "terminate called" in line or "quit called" in line:
            return True
        if "can't allocate region" in line:
            return True

    for line in out:
        if line.startswith("It's looking good!") or line.startswith("jsfunfuzz broke its own scripting environment: "):
            return True
        if line.startswith("Found a bug: "):
            return True

    return False


def hitMemoryLimit(err):
    """Does stderr indicate hitting a memory limit?"""

    if "ReportOverRecursed called" in err:
        # --enable-more-deterministic
        return "ReportOverRecursed called"
    elif "ReportOutOfMemory called" in err:
        # --enable-more-deterministic
        return "ReportOutOfMemory called"
    elif "failed to allocate" in err:
        # ASan
        return "failed to allocate"
    elif "can't allocate region" in err:
        # malloc
        return "can't allocate region"

    return None


def oomed(err):
    # spidermonkey shells compiled with --enable-more-deterministic will tell us on stderr if they run out of memory
    for line in err:
        if hitMemoryLimit(line):
            return True
    return False


def summaryString(issues, level, elapsedtime):
    amissDetails = ("") if (len(issues) == 0) else (" | " + repr(issues[:5]) + " ")
    return "%5.1fs | %d | %s%s" % (elapsedtime, level, JS_LEVEL_NAMES[level], amissDetails)


def truncateFile(fn, maxSize):
    if os.path.exists(fn) and os.path.getsize(fn) > maxSize:
        with open(fn, "r+") as f:
            f.truncate(maxSize)


def valgrindSuppressions(knownPath):
    return ["--suppressions=" + filename for filename in findIgnoreLists.findIgnoreLists(knownPath, "valgrind.txt")]


def deleteLogs(logPrefix):
    """Whoever calls baseLevel should eventually call deleteLogs (unless a bug was found)."""
    # If this turns up a WindowsError on Windows, remember to have excluded fuzzing locations in
    # the search indexer, anti-virus realtime protection and backup applications.
    os.remove(logPrefix + "-out.txt")
    os.remove(logPrefix + "-err.txt")
    if os.path.exists(logPrefix + "-crash.txt"):
        os.remove(logPrefix + "-crash.txt")
    if os.path.exists(logPrefix + "-vg.xml"):
        os.remove(logPrefix + "-vg.xml")
    # FIXME: in some cases, subprocesses.py gzips a core file only for us to delete it immediately.
    if os.path.exists(logPrefix + "-core.gz"):
        os.remove(logPrefix + "-core.gz")


def ulimitSet():
    '''When called as a preexec_fn, sets appropriate resource limits for the JS shell. Must only be called on POSIX.'''
    import resource  # module only available on POSIX

    # Limit address space to 2GB (or 1GB on ARM boards such as ODROID).
    GB = 2**30
    if sps.isARMv7l:
        resource.setrlimit(resource.RLIMIT_AS, (1*GB, 1*GB))
    else:
        resource.setrlimit(resource.RLIMIT_AS, (2*GB, 2*GB))

    # Limit corefiles to 0.5 GB.
    halfGB = int(GB / 2)
    resource.setrlimit(resource.RLIMIT_CORE, (halfGB, halfGB))


def parseOptions(args):
    parser = OptionParser()
    parser.disable_interspersed_args()
    parser.add_option("--valgrind",
                      action="store_true", dest="valgrind",
                      default=False,
                      help="use valgrind with a reasonable set of options")
    parser.add_option("--minlevel",
                      type="int", dest="minimumInterestingLevel",
                      default=JS_FINE + 1,
                      help="minimum js/jsInteresting.py level for lithium to consider the testcase interesting")
    parser.add_option("--timeout",
                      type="int", dest="timeout",
                      default=120,
                      help="timeout in seconds")
    options, args = parser.parse_args(args)
    if len(args) < 2:
        raise Exception("Not enough positional arguments")
    options.knownPath = args[0]
    options.jsengineWithArgs = args[1:]
    options.collector = createCollector.createCollector("jsfunfuzz")
    if not os.path.exists(options.jsengineWithArgs[0]):
        raise Exception("js shell does not exist: " + options.jsengineWithArgs[0])
    options.shellIsDeterministic = inspectShell.queryBuildConfiguration(options.jsengineWithArgs[0], 'more-deterministic')

    return options


# loopjsfunfuzz.py uses parseOptions and ShellResult [with inCompareJIT = False]
# compareJIT.py uses ShellResult [with inCompareJIT = True]

# For use by Lithium and autoBisect. (autoBisect calls init multiple times because it changes the js engine name)
def init(args):
    global gOptions
    gOptions = parseOptions(args)
def interesting(args, tempPrefix):
    options = gOptions
    # options, runthis, logPrefix, inCompareJIT
    res = ShellResult(options, options.jsengineWithArgs, tempPrefix, False)
    truncateFile(tempPrefix + "-out.txt", 1000000)
    truncateFile(tempPrefix + "-err.txt", 1000000)
    return res.lev >= gOptions.minimumInterestingLevel


# For direct, manual use
def main():
    options = parseOptions(sys.argv[1:])
    tempPrefix = "m"
    res = ShellResult(options, options.jsengineWithArgs, tempPrefix, False)
    print res.lev
if __name__ == "__main__":
    main()

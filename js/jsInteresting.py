#!/usr/bin/env python

from __future__ import with_statement

import os
import sys

from optparse import OptionParser

p0 = os.path.dirname(os.path.abspath(__file__))
p1 = os.path.abspath(os.path.join(p0, os.pardir, 'interestingness'))
sys.path.append(p1)
import timedRun
p2 = os.path.abspath(os.path.join(p0, os.pardir, "detect"))
sys.path.append(p2)
import detect_assertions
import detect_interesting_crashes
import detect_malloc_errors

# Levels of unhappiness.
# These are in order from "most expected to least expected" rather than "most ok to worst".
# Fuzzing will note the level, and pass it to Lithium.
# Lithium is allowed to go to a higher level.
(  JS_FINE,
   JS_KNOWN_CRASH, JS_TIMED_OUT,                          # frustrates understanding of stdout; not even worth reducing
   JS_ABNORMAL_EXIT,                                      # frustrates understanding of stdout; can mean several things
   JS_DID_NOT_FINISH, JS_DECIDED_TO_EXIT,                 # specific to jsfunfuzz
   JS_OVERALL_MISMATCH,                                   # specific to comparejit (set in compareJIT.py)
   JS_VG_AMISS, JS_MALLOC_ERROR, JS_NEW_ASSERT_OR_CRASH   # stuff really going wrong
) = range(10)


VALGRIND_ERROR_EXIT_CODE = 77

def baseLevel(runthis, timeout, knownPath, logPrefix, valgrind=False):
    if valgrind:
        runthis = ([
            "valgrind",
            "--error-exitcode=" + str(VALGRIND_ERROR_EXIT_CODE),
            "--gen-suppressions=all",
            "--leak-check=full",
            "--smc-check=all-non-file"  # Added by default because IonMonkey turns JITs on by default.
          ] +
            valgrindSuppressions(knownPath) +
            (["--dsymutil=yes"] if sys.platform=='darwin' else []) +
          runthis)
        #print " ".join(runthis)

    runinfo = timedRun.timed_run(runthis, timeout, logPrefix)
    sta = runinfo.sta

    lev = JS_FINE
    issues = []

    if detect_malloc_errors.amiss(logPrefix):
        issues.append("malloc error")
        lev = max(lev, JS_MALLOC_ERROR)

    if valgrind and runinfo.rc == VALGRIND_ERROR_EXIT_CODE:
        issues.append("valgrind reported an error")
        lev = max(lev, JS_VG_AMISS)

    if detect_assertions.amiss(knownPath, logPrefix, True):
        issues.append("unknown assertion")
        lev = max(lev, JS_NEW_ASSERT_OR_CRASH)
    elif sta == timedRun.CRASHED:
        if detect_interesting_crashes.amiss(knownPath, logPrefix + "-crash", True, runinfo.msg):
            if detect_assertions.amiss(knownPath, logPrefix, False, ignoreKnownAssertions=False):
                issues.append("treating known assertion as a known crash")
                lev = max(lev, JS_KNOWN_CRASH)
            else:
                issues.append("unknown crash")
                lev = max(lev, JS_NEW_ASSERT_OR_CRASH)
        else:
            issues.append("known crash")
            lev = max(lev, JS_KNOWN_CRASH)
    elif sta == timedRun.TIMED_OUT:
        issues.append("timed out")
        lev = max(lev, JS_TIMED_OUT)
    elif sta == timedRun.ABNORMAL and not (valgrind and runinfo.rc == VALGRIND_ERROR_EXIT_CODE):
        issues.append("abnormal exit")
        lev = max(lev, JS_ABNORMAL_EXIT)

    return (lev, issues, runinfo)


def jsfunfuzzLevel(options, logPrefix, quiet=False):
    (lev, issues, runinfo) = baseLevel(options.jsengineWithArgs, options.timeout, options.knownPath, logPrefix, valgrind=options.valgrind)

    if lev == JS_FINE:
        # Read in binary mode, because otherwise Python on Windows will
        # throw a fit when it encounters certain unicode.  Note that this
        # makes line endings platform-specific.
        with open(logPrefix + "-out", "rb") as f:
            for line in f:
                if (line.rstrip() == "It's looking good!"):
                    break
                elif (line.rstrip() == "jsfunfuzz stopping due to above error!"):
                    lev = JS_DECIDED_TO_EXIT
                    issues.append("jsfunfuzz decided to exit")
            else:
                issues.append("jsfunfuzz didn't finish")
                lev = JS_DID_NOT_FINISH

    if lev < JS_ABNORMAL_EXIT:
        vdump("jsfunfuzzLevel is ignoring a baseLevel of " + str(lev))
        lev = JS_FINE
        issues = []

    if lev != JS_FINE:
        # write issues to file
        pass

    if not quiet:
        print logPrefix + ": " + summaryString(issues, runinfo)
    return lev

def summaryString(issues, runinfo):
    amissStr = ("") if (len(issues) == 0) else ("*" + repr(issues) + " ")
    return "%s%s (%.1f seconds)" % (amissStr, runinfo.msg, runinfo.elapsedtime)

def truncateFile(fn, maxSize):
    if os.path.exists(fn) and os.path.getsize(fn) > maxSize:
        with open(fn, "r+") as f:
            f.truncate(maxSize)

def valgrindSuppressions(knownPath):
    a = []
    while os.path.basename(knownPath) != "known":
        filename = os.path.join(knownPath, "valgrind.txt")
        if os.path.exists(filename):
             a.append("--suppressions=" + filename)
        knownPath = os.path.dirname(os.path.dirname(filename))
    return a

def parseOptions(args):
    parser = OptionParser()
    parser.disable_interspersed_args()
    parser.add_option("--valgrind",
                      action = "store_true", dest = "valgrind",
                      default = False,
                      help = "use valgrind with a reasonable set of options")
    parser.add_option("--minlevel",
                      type = "int", dest = "minimumInterestingLevel",
                      default = JS_FINE + 1,
                      help = "minimum js/jsInteresting.py level for lithium to consider the testcase interesting")
    parser.add_option("--timeout",
                      type = "int", dest = "timeout",
                      default = 120,
                      help = "timeout in seconds")
    options, args = parser.parse_args(args)
    if len(args) < 2:
        raise Exception("Not enough positional arguments")
    options.knownPath = args[0]
    options.jsengineWithArgs = args[1:]
    if not os.path.exists(options.jsengineWithArgs[0]):
        raise Exception("js shell does not exist: " + options.jsengineWithArgs[0])
    return options


# loopjsfunfuzz.py uses parseOptions and jsfunfuzzLevel
# compareJIT.py uses baseLevel

# For use by Lithium and autoBisect. (autoBisect calls init multiple times because it changes the js engine name)
def init(args):
    global gOptions
    gOptions = parseOptions(args)
def interesting(args, tempPrefix):
    actualLevel = jsfunfuzzLevel(gOptions, tempPrefix, quiet=True)
    truncateFile(tempPrefix + "-out", 1000000)
    truncateFile(tempPrefix + "-err", 1000000)
    return actualLevel >= gOptions.minimumInterestingLevel

if __name__ == "__main__":
    options = parseOptions(sys.argv[1:])
    print jsfunfuzzLevel(options, "m")

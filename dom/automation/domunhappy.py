#!/usr/bin/env python

import os, sys
import detect_assertions, detect_malloc_errors, detect_interesting_crashes, detect_leaks, detect_valgrind_errors

p0=os.path.dirname(sys.argv[0])
p2=os.path.abspath(os.path.join(p0, "..", "..", "lithium"))
sys.path.append(p2)
import ntr


# Levels of unhappiness.
# These are in order from "most expected to least expected" rather than "most ok to worst".
# Fuzzing will note the level, and pass it to Lithium.
# Lithium is allowed to go to a higher level.
(DOM_FINE, DOM_TIMED_OUT, DOM_ABNORMAL_EXIT, DOM_VG_AMISS, DOM_NEW_LEAK, DOM_MALLOC_ERROR, DOM_NEW_ASSERT_OR_CRASH) = range(7)



def level(runthis, timeout, knownPath, logPrefix):
    if runthis[0] == "valgrind":
        runthis = [
            "valgrind",
            "--xml=yes",
            "--xml-file=" + logPrefix + "-vg.xml",
            "--suppressions=" + os.path.join(knownPath, "valgrind.txt"),
            "--gen-suppressions=all",
            "--dsymutil=yes"
        ] + runthis[1:]

    runinfo = ntr.timed_run(runthis, timeout, logPrefix)
    (sta, msg, elapsedtime) = (runinfo.sta, runinfo.msg, runinfo.elapsedtime)

    lev = DOM_FINE
    issues = []

    if detect_assertions.amiss(logPrefix, False):
        issues.append("unknown assertion")
        lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)
    if sta == ntr.CRASHED and detect_interesting_crashes.amiss(logPrefix, False, msg):
        issues.append("unknown crash")
        lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)
    if runthis[0] != "valgrind" and sta == ntr.NORMAL and detect_leaks.amiss(logPrefix):
        issues.append("unknown leak")
        lev = max(lev, DOM_NEW_LEAK)
    if detect_malloc_errors.amiss(logPrefix):
        issues.append("malloc error")
        lev = max(lev, DOM_MALLOC_ERROR)
    if sta == ntr.ABNORMAL:
        issues.append("abnormal exit")
        lev = max(lev, DOM_ABNORMAL_EXIT)
    if sta == ntr.TIMED_OUT:
        issues.append("timed out")
        lev = max(lev, DOM_TIMED_OUT)
    if runthis[0] == "valgrind" and detect_valgrind_errors.amiss(logPrefix + "-vg.xml", True):
        issues.append("valgrind reported an error")
        lev = max(lev, DOM_VG_AMISS)

    amiss = len(issues) != 0
    amissStr = "" if not amiss else "*" + repr(issues) + " "
    print "%s: %s%s (%.1f seconds)" % (logPrefix, amissStr, msg, elapsedtime)
    return lev


def interesting(args, tempPrefix):
    minimumInterestingLevel = int(args[0])
    timeout = int(args[1])
    knownPath = args[2]
    actualLevel = level(args[3:], timeout, knownPath, tempPrefix)
    return actualLevel >= minimumInterestingLevel

def init(args):
    initWithKnownPath(args[2])

def initWithKnownPath(knownPath):
    detect_assertions.init(knownPath)
    detect_interesting_crashes.init(knownPath)

if __name__ == "__main__":
    timeout = int(sys.argv[1])
    knownPath = sys.argv[2]
    logPrefix = "t1"
    runThis = sys.argv[3:]
    initWithKnownPath(knownPath)
    level(runThis, timeout, knownPath, logPrefix)

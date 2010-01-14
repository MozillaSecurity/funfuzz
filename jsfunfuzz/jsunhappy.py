#!/usr/bin/env python

import os, sys
import ntr

p0=os.path.dirname(sys.argv[0])
p1=os.path.abspath(os.path.join(p0, "..", "dom", "automation"))

sys.path.append(p1)

import detect_assertions, detect_malloc_errors, detect_interesting_crashes, detect_valgrind_errors


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



def baseLevel(runthis, timeout, knownPath, logPrefix):
    if runthis[0] == "valgrind":
        runthis = [
            "valgrind",
            "--xml=yes",
            "--xml-file=" + logPrefix + "-vg.xml",
            "--suppressions=" + os.path.join(knownPath, "valgrind.txt"),
            "--gen-suppressions=all",
            "--dsymutil=yes",
            "--smc-check=all", # needed for -j if i don't use --enable-valgrind to build js
        ] + runthis[1:]

    runinfo = ntr.timed_run(runthis, timeout, logPrefix)
    sta = runinfo.sta

    lev = JS_FINE
    issues = []
    
    if detect_assertions.amiss(knownPath, logPrefix, True):
        issues.append("unknown assertion")
        lev = max(lev, JS_NEW_ASSERT_OR_CRASH)
    if sta == ntr.CRASHED and lev != JS_NEW_ASSERT_OR_CRASH:
        if detect_interesting_crashes.amiss(knownPath, logPrefix + "-crash", True, runinfo.msg):
            if detect_assertions.amiss(knownPath, logPrefix, False, ignoreKnownAssertions=False):
                print "Warning: detect_interesting_crashes complained but there was a fatal assertion"
            else:
                issues.append("unknown crash")
                lev = max(lev, JS_NEW_ASSERT_OR_CRASH)
        else:
            issues.append("known crash")
            lev = max(lev, JS_KNOWN_CRASH)
    if detect_malloc_errors.amiss(logPrefix):
        issues.append("malloc error")
        lev = max(lev, JS_MALLOC_ERROR)
    if sta == ntr.ABNORMAL:
        issues.append("abnormal exit")
        lev = max(lev, JS_ABNORMAL_EXIT)
    if sta == ntr.TIMED_OUT:
        issues.append("timed out")
        lev = max(lev, JS_TIMED_OUT)
    if runthis[0] == "valgrind" and detect_valgrind_errors.amiss(logPrefix + "-vg.xml", False):
        issues.append("valgrind reported an error")
        lev = max(lev, JS_VG_AMISS)

    return (lev, issues, runinfo)


def jsfunfuzzLevel(runthis, timeout, knownPath, logPrefix):
    (lev, issues, runinfo) = baseLevel(runthis, timeout, knownPath, logPrefix)

    if lev == JS_FINE:
        logfile = open(logPrefix + "-out", "r")
        for line in logfile:
            if (line == "It's looking good!\n"):
                break
            elif (line == "jsfunfuzz stopping due to above error!\n"):
                lev = JS_DECIDED_TO_EXIT
                issues.append("jsfunfuzz decided to exit")
        else:
            issues.append("jsfunfuzz didn't finish")
            lev = JS_DID_NOT_FINISH
        logfile.close()

    amiss = len(issues) != 0
    amissStr = "" if not amiss else "*" + repr(issues) + " "
    print "%s: %s%s (%.1f seconds)" % (logPrefix, amissStr, runinfo.msg, runinfo.elapsedtime)
    return lev


# For use by Lithium
def interesting(args, tempPrefix):
    minimumInterestingLevel = int(args[0])
    timeout = int(args[1])
    knownPath = args[2]
    actualLevel = jsfunfuzzLevel(args[3:], timeout, knownPath, tempPrefix)
    return actualLevel >= minimumInterestingLevel

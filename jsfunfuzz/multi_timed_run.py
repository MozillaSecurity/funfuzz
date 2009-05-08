import os, sys

p0=os.path.dirname(sys.argv[0])
p1=os.path.abspath(os.path.join(p0, "..", "dom", "automation"))
p2=os.path.abspath(os.path.join(p0, "..", "lithium"))

sys.path.append(p1)
sys.path.append(p2)

import detect_assertions, detect_malloc_errors, detect_interesting_crashes
import ntr

knownPath = os.path.expanduser(sys.argv[2])

def succeeded(logPrefix):
    logfile = open(logPrefix + "-out", "r")
    for line in logfile:
        if (line == "It's looking good!\n"):
            return True
    return False


def showtail(filename):
    cmd = "tail -n 20 %s" % filename
    print cmd
    print ""
    os.system(cmd)
    print ""
    print ""


def many_timed_runs():
    iteration = 0
    while True:
        iteration += 1
        logPrefix = "w%d" % iteration

        runinfo = ntr.timed_run(sys.argv[3:], int(sys.argv[1]), logPrefix)
        (sta, msg, elapsedtime) = (runinfo.sta, runinfo.msg, runinfo.elapsedtime)

        issues = []

        if detect_assertions.amiss(logPrefix, True):
          issues.append("unknown assertion")
        if sta == ntr.CRASHED and detect_interesting_crashes.amiss(logPrefix, True, msg):
          issues.append("unknown crash")
        if detect_malloc_errors.amiss(logPrefix):
          issues.append("malloc error")

        if len(issues) == 0 and sta == ntr.NORMAL and not succeeded(logPrefix):
          issues.append("nothing really bad happened, yet jsfunfuzz didn't finish")
        if sta == ntr.ABNORMAL:
          issues.append("abnormal exit")
        if sta == ntr.TIMED_OUT:
          issues.append("timed out")

        amiss = len(issues) != 0
        amissStr = "" if not amiss else "*" + repr(issues) + " "
        print "%s: %s%s (%.1f seconds)" % (logPrefix, amissStr, msg, elapsedtime)

        if amiss:
            showtail(logPrefix + "-out")
            showtail(logPrefix + "-err")
            print ""
        else:
            os.remove(logPrefix + "-out")
            os.remove(logPrefix + "-err")
            if (os.path.exists(logPrefix + "-crash")):
                os.remove(logPrefix + "-crash")
            if (os.path.exists(logPrefix + "-core")):
                os.remove(logPrefix + "-core")

detect_assertions.init(knownPath)
detect_interesting_crashes.init(knownPath)
many_timed_runs()

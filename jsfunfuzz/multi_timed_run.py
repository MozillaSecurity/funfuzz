import os, sys
sys.path.append(os.path.dirname(sys.argv[0]) + "/../dom/automation/")
import detect_assertions, detect_malloc_errors, detect_interesting_crashes
sys.path.append(os.path.dirname(sys.argv[0]) + "/../lithium/")
import ntr


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
        (sta, msg, elapsedtime) = ntr.timed_run(sys.argv[2:], int(sys.argv[1]), logPrefix)
        issues = []

        if detect_assertions.amiss(logPrefix):
          issues.append("unknown assertion")
        if sta == ntr.CRASHED and detect_interesting_crashes.amiss(logPrefix, msg):
          issues.append("unknown crash")
        if detect_malloc_errors.amiss(logPrefix):
          issues.append("malloc error")

        if len(issues) == 0 and sta == ntr.NORMAL and not succeeded(logPrefix):
          issues.append("nothing really bad happened, yet jsfunfuzz didn't finish")
        if sta == ntr.ABNORMAL:
          issues.append("abnormal exit")
          
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

many_timed_runs()

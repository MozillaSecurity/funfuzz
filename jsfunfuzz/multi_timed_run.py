import os, sys
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
        print "%s: %s (%.1f seconds)" % (logPrefix, msg, elapsedtime)
        if not succeeded(logPrefix):
            showtail(logPrefix + "-out")
            showtail(logPrefix + "-err")
        else:
            os.remove(logPrefix + "-out")
            os.remove(logPrefix + "-err")


many_timed_runs()

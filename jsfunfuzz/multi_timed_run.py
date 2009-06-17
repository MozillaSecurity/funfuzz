#!/usr/bin/env python -u

import os, sys, subprocess

p0=os.path.dirname(sys.argv[0])
p2=os.path.abspath(os.path.join(p0, "..", "lithium"))
sys.path.append(p2)
lithiumpy = os.path.join(p2, "lithium.py")
jsunhappypy = os.path.join(p0, "jsunhappy.py")

import jsunhappy

timeout = int(sys.argv[1])
knownPath = os.path.expanduser(sys.argv[2])
runThis = sys.argv[3:]
jsfunfuzzPath = runThis[-1]

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

        level = jsunhappy.level(runThis, timeout, logPrefix)

        if level > jsunhappy.JS_TIMED_OUT:
            showtail(logPrefix + "-out")
            showtail(logPrefix + "-err")
            
            # splice jsfunfuzz.js with `grep FRC wN-out`
            filenameToReduce = logPrefix + "-reduced.js"
            [before, after] = fuzzSplice(open(jsfunfuzzPath))
            newfileLines = before + linesWith(open(logPrefix + "-out"), "FRC") + after
            writeLinesToFile(newfileLines, logPrefix + "-orig.js")
            writeLinesToFile(newfileLines, filenameToReduce)
            
            # Run Lithium as a subprocess: reduce to the smallest file that has at least the same unhappiness level
            lithArgs = [jsunhappypy, str(level), str(timeout), knownPath] + runThis[:-1] + [filenameToReduce]
            print "multi_timed_run is running Lithium..."
            print repr([lithiumpy] + lithArgs)
            subprocess.call([lithiumpy] + lithArgs, stdout=open(logPrefix + "lith1", "w"))
            if level > jsunhappy.JS_DID_NOT_FINISH:
                subprocess.call([lithiumpy, "-c"] + lithArgs, stdout=open(logPrefix + "lith2", "w"))
            print "Done running Lithium"

        else:
            os.remove(logPrefix + "-out")
            os.remove(logPrefix + "-err")
            if (os.path.exists(logPrefix + "-crash")):
                os.remove(logPrefix + "-crash")
            if (os.path.exists(logPrefix + "-core")):
                os.remove(logPrefix + "-core")


def fuzzSplice(file):
    '''Returns the lines of a file, minus the ones between lines containing SPLICE'''
    before = []
    after = []
    for line in file:
        before.append(line)
        if line.find("SPLICE") != -1:
            break
    for line in file:
        if line.find("SPLICE") != -1:
            after.append(line)
            break
    for line in file:
        after.append(line)
    file.close()
    return [before, after]


def linesWith(file, searchFor):
    '''Returns the lines from a file that contain a given string'''
    matchingLines = []
    for line in file:
        if line.find(searchFor) != -1:
            matchingLines.append(line)
    file.close()
    return matchingLines


def writeLinesToFile(lines, filename):
      f = open(filename, "w")
      f.writelines(lines)
      f.close()

jsunhappy.initWithKnownPath(knownPath)
many_timed_runs()

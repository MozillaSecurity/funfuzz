#!/usr/bin/env python

import os, sys, subprocess

p0=os.path.dirname(sys.argv[0])
p2=os.path.abspath(os.path.join(p0, "..", "lithium"))
sys.path.append(p2)
lithiumpy = os.path.join(p2, "lithium.py")
jsunhappypy = os.path.join(p0, "jsunhappy.py")

import jsunhappy
import compareJIT

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
        logPrefix = tempDir + os.sep + "w" + str(iteration)

        level = jsunhappy.level(runThis, timeout, knownPath, logPrefix)

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
            lith1tmp = logPrefix + "-lith1-tmp"
            os.mkdir(lith1tmp)
            lithArgs = [jsunhappypy, str(level), str(timeout), knownPath] + runThis[:-1] + [filenameToReduce]
            print "multi_timed_run is running Lithium..."
            print repr([lithiumpy] + lithArgs)
            subprocess.call(["python", lithiumpy, "--tempdir=" + lith1tmp] + lithArgs, stdout=open(logPrefix + "-lith1-out", "w"))
            if level > jsunhappy.JS_DID_NOT_FINISH:
                lith2tmp = logPrefix + "-lith2-tmp"
                os.mkdir(lith2tmp)
                subprocess.call(["python", lithiumpy, "--tempdir=" + lith2tmp, "-c"] + lithArgs, stdout=open(logPrefix + "-lith2-out", "w"))
            print "Done running Lithium"

        else:
            if level == jsunhappy.JS_FINE:
                # Bug 496816 explains why we disable compareJIT on Linux.
                if os.name != "posix" or os.uname()[0] != "Linux":
                    jitcomparelines = linesWith(open(logPrefix + "-out"), "FCM") + ["try{print(uneval(this));}catch(e){}"]
                    jitcomparefilename = logPrefix + "-cmpin.js"
                    writeLinesToFile(jitcomparelines, jitcomparefilename)
                    compareJIT.compareJIT(runThis[0], jitcomparefilename, logPrefix)
            os.remove(logPrefix + "-out")
            os.remove(logPrefix + "-err")
            if (os.path.exists(logPrefix + "-crash")):
                os.remove(logPrefix + "-crash")
            if (os.path.exists(logPrefix + "-vg.xml")):
                os.remove(logPrefix + "-vg.xml")
            if (os.path.exists(logPrefix + "-core")):
                os.remove(logPrefix + "-core")
            if (os.path.exists(logPrefix + "-cmpin.js")):
                os.remove(logPrefix + "-cmpin.js")


def fuzzSplice(file):
    '''Returns the lines of a file, minus the ones between the two lines containing SPLICE'''
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

def createTempDir():
    global tempDir
    i = 1
    while 1:
        tempDir = "wtmp" + str(i)
        # To avoid race conditions, we use try/except instead of exists/create
        # Hopefully we don't get any errors other than "File exists" :)
        try:
            os.mkdir(tempDir)
            break
        except OSError, e:
            i += 1
    print tempDir + os.sep


jsunhappy.initWithKnownPath(knownPath)
createTempDir()
many_timed_runs()

#!/usr/bin/env python

import os, sys, subprocess
from optparse import OptionParser

p0=os.path.dirname(__file__)
jsunhappypy = os.path.join(p0, "jsunhappy.py")

import jsunhappy
import pinpoint
import compareJIT

parser = OptionParser()
parser.disable_interspersed_args()
parser.add_option("--comparejit",
                  action = "store_true", dest = "useCompareJIT",
                  default = False,
                  help = "After running the fuzzer, run the FCM lines against the engine in two configurations and compare the output.")
parser.add_option("--fuzzjs",
                  action = "store", dest = "fuzzjs",
                  default = os.path.join(p0, "jsfunfuzz.js"),
                  help = "Which fuzzer to run (e.g. jsfunfuzz.js or regexpfuzz.js)")
parser.add_option("--repo",
                  action = "store", dest = "repo",
                  default = os.path.expanduser("~/tracemonkey/"),
                  help = "The hg repository (e.g. ~/tracemonkey/), for bisection")
options, args = parser.parse_args(sys.argv[1:])

timeout = int(args[0])
knownPath = os.path.expanduser(args[1])
engine = args[2]
engineFlags = args[3:]
runThis = [engine] + engineFlags + ["-e", "maxRunTime=" + str(timeout*(1000/2)), "-f", options.fuzzjs]

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

        level = jsunhappy.jsfunfuzzLevel(runThis, timeout, knownPath, logPrefix)

        oklevel = jsunhappy.JS_KNOWN_CRASH
        if options.fuzzjs.find("jsfunfuzz") != -1:
            # Allow hangs. Allow abnormal exits in js shell (OOM) and xpcshell (bug 613142).
            oklevel = jsunhappy.JS_ABNORMAL_EXIT

        if level > oklevel:
            showtail(logPrefix + "-out")
            showtail(logPrefix + "-err")
            
            # splice jsfunfuzz.js with `grep FRC wN-out`
            filenameToReduce = logPrefix + "-reduced.js"
            [before, after] = fuzzSplice(open(options.fuzzjs))
            newfileLines = before + linesWith(open(logPrefix + "-out"), "FRC") + after
            writeLinesToFile(newfileLines, logPrefix + "-orig.js")
            writeLinesToFile(newfileLines, filenameToReduce)
            
            # Run Lithium and autobisect (make a reduced testcase and find a regression window)
            itest = [jsunhappypy, str(level), str(timeout), knownPath]
            alsoRunChar = (level > jsunhappy.JS_DID_NOT_FINISH)
            pinpoint.pinpoint(itest, logPrefix, engine, engineFlags, filenameToReduce, options.repo, alsoRunChar=alsoRunChar)

        else:
            if options.useCompareJIT and level == jsunhappy.JS_FINE:
                jitcomparelines = linesWith(open(logPrefix + "-out"), "FCM") + ["try{print(uneval(this));}catch(e){}"]
                jitcomparefilename = logPrefix + "-cj-in.js"
                writeLinesToFile(jitcomparelines, jitcomparefilename)
                compareJIT.compareJIT(engine, jitcomparefilename, logPrefix + "-cj", knownPath, options.repo, timeout, deleteBoring=True)
            os.remove(logPrefix + "-out")
            os.remove(logPrefix + "-err")
            if (os.path.exists(logPrefix + "-crash")):
                os.remove(logPrefix + "-crash")
            if (os.path.exists(logPrefix + "-vg.xml")):
                os.remove(logPrefix + "-vg.xml")
            if (os.path.exists(logPrefix + "-core")):
                os.remove(logPrefix + "-core")


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


createTempDir()
many_timed_runs()

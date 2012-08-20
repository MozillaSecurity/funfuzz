#!/usr/bin/env python

from __future__ import with_statement
import os, sys, platform, signal
ready = False

def amiss(knownPath, crashLogFilename, verbose, msg):
    if not ready:
        readIgnoreLists(knownPath)

    resetCounts()

    igmatch = []

    if os.path.exists(crashLogFilename):
        with open(crashLogFilename, "r") as f:
            for line in f:
                if isKnownCrashSignature(line):
                    igmatch.append(line.rstrip())

        if len(igmatch) == 0:
            # Would be great to print [@ nsFoo::Bar] in addition to the filename, but
            # that would require understanding the crash log format much better than
            # this script currently does.
            print "Unknown crash: " + crashLogFilename
            return True
        else:
            if verbose:
                print "@ Known crash: " + ", ".join(igmatch[0:5])
            return False
    else:
        print "Unknown crash (crash log is missing)"
        return True

TOO_MUCH_RECURSION_MAGIC = "[TMR] "

def readIgnoreLists(knownPath):
    global ignoreList
    global ready
    ignoreList = []
    while os.path.basename(knownPath) != "known":
        filename = os.path.join(knownPath, "crashes.txt")
        if os.path.exists(filename):
             readIgnoreList(filename)
        knownPath = os.path.dirname(os.path.dirname(filename))
    ready = True
    #print "detect_interesting_crashes is ready (ignoring %d strings)" % (len(ignoreList))

def readIgnoreList(filename):
    with open(filename) as ignoreFile:
        for line in ignoreFile:
            line = line.rstrip()
            if line.startswith(TOO_MUCH_RECURSION_MAGIC):
                ignoreList.append({"seenCount": 0, "needCount": 20, "theString": line[len(TOO_MUCH_RECURSION_MAGIC):]})
            elif len(line) > 0 and not line.startswith("#"):
                ignoreList.append({"seenCount": 0, "needCount": 1,  "theString": line})

def isKnownCrashSignature(line):
    global ignoreList
    for ig in ignoreList:
        if line.find(ig["theString"]) != -1:
            ig["seenCount"] += 1
            if ig["seenCount"] >= ig["needCount"]:
                return True
    return False

def resetCounts():
    global ignoreList
    for ig in ignoreList:
        ig["seenCount"] = 0

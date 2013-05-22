#!/usr/bin/env python

import os
ready = False

def amiss(knownPath, crashLogFilename, verbose):
    if not ready:
        readIgnoreLists(knownPath)

    resetCounts()

    igmatch = []

    if os.path.exists(crashLogFilename):
        with open(crashLogFilename, "r") as f:
            for line in f:
                if isKnownCrashSignature(line, False):
                    igmatch.append(line.rstrip())
                    if verbose:
                        print "@ Known crash: " + line.rstrip()

        if len(igmatch) == 0:
            # Would be great to print [@ nsFoo::Bar] in addition to the filename, but
            # that would require understanding the crash log format much better than
            # this script currently does.
            print "Unknown crash: " + crashLogFilename
            return True
        else:
            return False
    else:
        print "Unknown crash (crash log is missing)"
        return True

TOO_MUCH_RECURSION_MAGIC = "[TMR] "
EXPLOITABLE_MAGIC = "[EXPLOITABLE] "

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
            needCount = 0
            exploitable = False
            if line.startswith("#") or len(line) == 0:
                continue
            if line.startswith(TOO_MUCH_RECURSION_MAGIC):
                line = line[len(TOO_MUCH_RECURSION_MAGIC):]
                needCount = 20
            if line.startswith(EXPLOITABLE_MAGIC):
                line = line[len(EXPLOITABLE_MAGIC):]
                exploitable = True
            if line.startswith("["):
                raise Exception("Typo in crashes.txt?")
            ignoreList.append({"seenCount": 0, "needCount": needCount, "exploitable": exploitable, "theString": line})

def isKnownCrashSignature(line, exploitable):
    global ignoreList
    for ig in ignoreList:
        if not exploitable or ig["exploitable"]: # If the caller says the crash is exploitable, only consider crashes.txt entries marked 'exploitable'.
            if line.find(ig["theString"]) != -1:
                ig["seenCount"] += 1
                if ig["seenCount"] >= ig["needCount"]:
                    return True
    return False

def resetCounts():
    global ignoreList
    for ig in ignoreList:
        ig["seenCount"] = 0

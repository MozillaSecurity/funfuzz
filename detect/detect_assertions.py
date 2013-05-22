#!/usr/bin/env python

# Recognizes NS_ASSERTIONs based on condition, text, and filename (ignoring irrelevant parts of the path)
# Recognizes JS_ASSERT based on condition only :(
# Recognizes ObjC exceptions based on message, since there is no stack information available, at least on Tiger.

import os, sys

simpleIgnoreList = []
twoPartIgnoreList = []
ready = False

# Called directly by domInteresting.py
def scanLine(knownPath, line):
    global ignoreList
    if not ready:
        readIgnoreLists(knownPath)

    line = line.strip("\x07").rstrip("\n")

    if assertiony(line) and not ignore(line):
        return True

    return False

# FIXME: scanFile is now dead code
def scanFile(knownPath, currentFile, verbose, ignoreKnownAssertions):
    global ignoreList
    if not ready:
        readIgnoreLists(knownPath)

    foundSomething = False

    # map from (assertion message) to (true, if seen in the current file)
    seenInCurrentFile = {}

    for line in currentFile:
        line = line.strip("\x07").rstrip("\n")
        if (assertiony(line) and not (line in seenInCurrentFile)):
            seenInCurrentFile[line] = True
            if not (ignore(line)):
                print "! New assertion: "
                print line
                foundSomething = True
            elif not ignoreKnownAssertions:
                foundSomething = True
            elif verbose:
                print "@ Known assertion: "
                print line

    currentFile.close()

    return foundSomething

def assertiony(line):
    return (line.startswith("###!!!") or # NS_ASSERTION and also aborts
            line.startswith("Assertion failure:") or # spidermonkey; nss
            line.find("Assertion failed:") != -1 or # assert.h e.g. as used by harfbuzz
            line.find("Mozilla has caught an Obj-C exception") != -1
           )

def readIgnoreLists(knownPath):
    global ready
    while os.path.basename(knownPath) != "known":
        filename = os.path.join(knownPath, "assertions.txt")
        if os.path.exists(filename):
             readIgnoreList(filename)
        knownPath = os.path.dirname(os.path.dirname(filename))
    ready = True
    print "detect_assertions is ready (ignoring %d strings without filenames and %d strings with filenames)" % (len(simpleIgnoreList), len(twoPartIgnoreList))

def readIgnoreList(filename):
    global ready
    with open(filename) as ignoreFile:
        for line in ignoreFile:
            line = line.rstrip()
            if ((len(line) > 0) and not line.startswith("#")):
                mpi = line.find(", file ")  # NS_ASSERTION and friends use this format
                if (mpi == -1):
                    mpi = line.find(": file ")  # NS_ABORT uses this format
                if (mpi == -1):
                    simpleIgnoreList.append(line)
                else:
                    twoPartIgnoreList.append((line[:mpi+7], line[mpi+7:]))
    ready = True


def ignore(assertion):
    global simpleIgnoreList
    for ig in simpleIgnoreList:
        if assertion.find(ig) != -1:
            return True
    for (part1, part2) in twoPartIgnoreList:
        if assertion.find(part1) != -1 and assertion.replace('\\', '/').find(part2) != -1:
            return True
    return False


# For use by af_timed_run and jsunhappy.py
def amiss(knownPath, logPrefix, verbose, ignoreKnownAssertions=True):
    with open(logPrefix + "-err.txt") as currentFile:
        return scanFile(knownPath, currentFile, verbose, ignoreKnownAssertions)

# For standalone use
if __name__ == "__main__":
    knownPath = sys.argv[1]
    with open(sys.argv[2]) as currentFile:
        print scanFile(knownPath, currentFile, False, True)

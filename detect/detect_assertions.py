#!/usr/bin/env python

# Recognizes NS_ASSERTIONs based on condition, text, and filename (ignoring irrelevant parts of the path)
# (FuzzManager's AssertionHelper.py handles fatal assertions of all flavors.)

import findIgnoreLists
import re

simpleIgnoreList = []
twoPartIgnoreList = []
ready = False


# Called directly by domInteresting.py and jsInteresting.py
def scanLine(knownPath, line):
    global ignoreList
    if not ready:
        readIgnoreLists(knownPath)

    line = line.strip("\x07").rstrip("\n")

    if "###!!! ASSERT" in line:
        line = re.sub("^\\[\\d+\\]\\s+", "", line, count=1)  # Strip leading [PID], if present
        if assertionIsNew(line):
            return line

    return None


def readIgnoreLists(knownPath):
    global ready
    for filename in findIgnoreLists.findIgnoreLists(knownPath, "assertions.txt"):
        readIgnoreList(filename)
    ready = True
    print "detect_assertions is ready (ignoring %d strings without filenames and %d strings with filenames)" % (len(simpleIgnoreList), len(twoPartIgnoreList))


def readIgnoreList(filename):
    global ready
    with open(filename) as ignoreFile:
        for line in ignoreFile:
            line = line.rstrip()
            if (len(line) > 0) and not line.startswith("#"):
                mpi = line.find(", file ")
                if mpi == -1:
                    simpleIgnoreList.append(line)
                else:
                    twoPartIgnoreList.append((line[:mpi+7], line[mpi+7:]))
    ready = True


def assertionIsNew(assertion):
    global simpleIgnoreList
    for ig in simpleIgnoreList:
        if assertion.find(ig) != -1:
            return False
    for (part1, part2) in twoPartIgnoreList:
        if assertion.find(part1) != -1 and assertion.replace('\\', '/').find(part2) != -1:
            return False
    return True

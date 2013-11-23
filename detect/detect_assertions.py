#!/usr/bin/env python

# Recognizes NS_ASSERTIONs based on condition, text, and filename (ignoring irrelevant parts of the path)
# Recognizes JS_ASSERT based on condition only :(
# Recognizes ObjC exceptions based on message, since there is no stack information available, at least on Tiger.

import os, sys

simpleIgnoreList = []
twoPartIgnoreList = []
ready = False

(NO_ASSERT, NON_FATAL_ASSERT, FATAL_ASSERT) = range(3)

# Called directly by domInteresting.py and jsInteresting.py
# Returns (severity, new) where |severity| is the enum above and |new| is a bool
def scanLine(knownPath, line):
    global ignoreList
    if not ready:
        readIgnoreLists(knownPath)

    line = line.strip("\x07").rstrip("\n")

    severity = assertionSeverity(line)
    if severity == NO_ASSERT:
        return (NO_ASSERT, False)
    return (severity, assertionIsNew(line))

def assertionSeverity(line):
    if "###!!! ASSERT" in line:
        return NON_FATAL_ASSERT
    if "###!!! ABORT" in line:
        return FATAL_ASSERT
    if "Assertion failure:" in line:
         # MOZ_ASSERT; spidermonkey; nss
         return FATAL_ASSERT
    if "Assertion failed:" in line:
        # assert.h e.g. as used by harfbuzz
        return FATAL_ASSERT
    if "Mozilla has caught an Obj-C exception" in line:
        return NON_FATAL_ASSERT
    return NO_ASSERT

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


def assertionIsNew(assertion):
    global simpleIgnoreList
    for ig in simpleIgnoreList:
        if assertion.find(ig) != -1:
            return False
    for (part1, part2) in twoPartIgnoreList:
        if assertion.find(part1) != -1 and assertion.replace('\\', '/').find(part2) != -1:
            return False
    return True

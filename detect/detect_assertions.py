#!/usr/bin/env python

# Recognizes NS_ASSERTIONs based on condition, text, and filename (ignoring irrelevant parts of the path)
# Recognizes JS_ASSERT based on condition only :(
# Recognizes ObjC exceptions based on message, since there is no stack information available, at least on Tiger.

import findIgnoreLists

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

    if "Aborting on channel error" in line:
        # A child is aborting due to a crash in the parent.
        # It would be great if we could correctly detect both assertions and crashes in both parent and child processes,
        # but I have no clue how to do either.
        # (See bug 986379 for an example of a bug that can trigger it -- but only if privacy.sanitize.sanitizeOnShutdown is true??)
        return (NON_FATAL_ASSERT, False)
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
    if line.startswith("Assertion failed:"):
        # assert.h e.g. as used by harfbuzz
        # Lots of JS tests use this to indicate failure, but we don't care when transcluding those tests into fuzz testcases
        return FATAL_ASSERT
    if "Mozilla has caught an Obj-C exception" in line:
        return NON_FATAL_ASSERT
    return NO_ASSERT

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

#!/usr/bin/env python

# Recognizes NS_ASSERTIONs based on condition, text, and filename (ignoring irrelevant parts of the path)
# Recognizes JS_ASSERT based on condition only :(
# Recognizes ObjC exceptions based on message, since there is no stack information available, at least on Tiger.

import os, sys

simpleIgnoreList = []
twoPartIgnoreList = []

def fs(currentFile, verbose):
    global ignoreList

    foundSomething = False

    # map from (assertion message) to (true, if seen in the current file)
    seenInCurrentFile = {}

    for line in currentFile:
        line = line.strip("\x07").rstrip("\n")
        if (assertiony(line) and not (line in seenInCurrentFile)):
            seenInCurrentFile[line] = True
            if not (ignore(line)):
                print line
                foundSomething = True
            elif verbose:
                print "@ Known assertion: " + line

    currentFile.close()

    return foundSomething

def assertiony(line):
    return (line.startswith("###!!!") or # NS_ASSERTION and also aborts
             line.startswith("Assertion failure:") or # spidermonkey, nss
             line.find("Mozilla has caught an Obj-C exception") != -1 or
             line.find("Assertion failed:") != -1 or # nanojit
             line.find("failed assertion") != -1 # nanojit
            )

def init(knownPath):
    global simpleIgnoreList
    global twoPartIgnoreList
    ignoreFile = file(knownPath + "assertions.txt", "r")
    for line in ignoreFile:
        line = line.strip()
        if ((len(line) > 0) and not line.startswith("#")):
            mpi = line.find(", file ")  # NS_ASSERTION and friends use this format
            if (mpi == -1):
                mpi = line.find(": file ")  # NS_ABORT uses this format
            if (mpi == -1):
                simpleIgnoreList.append(line)
            else:
                twoPartIgnoreList.append((line[:mpi+7], line[mpi+7:].replace("/", os.sep)))
    ignoreFile.close()
    print "detect_assertions is ready (ignoring %d strings without filenames and %d strings with filenames)" % (len(simpleIgnoreList), len(twoPartIgnoreList))

        
def ignore(assertion):
    global simpleIgnoreList
    for ig in simpleIgnoreList:
        if assertion.find(ig) != -1:
            return True
    for (part1, part2) in twoPartIgnoreList:
        if assertion.find(part1) != -1 and assertion.find(part2) != -1:
            return True
    return False


# For use by af_timed_run
def amiss(logPrefix, verbose):
    currentFile = file(logPrefix + "-err", "r")
    return fs(currentFile, verbose)

# For standalone use
if __name__ == "__main__":
    init(sys.argv[1])
    currentFile = file(sys.argv[2], "r")
    fs(currentFile, False)

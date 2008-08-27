#!/usr/bin/env python

# Recognizes NS_ASSERTIONs based on condition, text, and filename (ignoring irrelevant parts of the path)
# Recognizes JS_ASSERT based on condition only :(
# Recognizes ObjC exceptions based on message, since there is no stack information available, at least on Tiger.

import os, sys


def fs(currentFile):
    global ignoreList

    foundSomething = False

    # map from (assertion message) to (true, if seen in the current file)
    seenInCurrentFile = {}

    for line in currentFile:
        line = line.strip("\x07").rstrip("\n")
        if ((line.startswith("###!!!") or 
             line.startswith("Assertion failure:") or # spidermonkey
             line.find("Mozilla has caught an Obj-C exception") != -1 or
             line.find("failed assertion") # nanojit
            ) and not (line in seenInCurrentFile)):
            seenInCurrentFile[line] = True
            if not (ignore(line)):
                print line
                foundSomething = True

    currentFile.close()
    
    return foundSomething


def getIgnores():

    global simpleIgnoreList
    ignoreFile = open(os.path.dirname(sys.argv[0]) + os.sep + "known_assertions.txt", "r")

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
                
def ignore(assertion):
    global simpleIgnoreList
    for ig in simpleIgnoreList:
        if assertion.find(ig) != -1:
            return True
    for (part1, part2) in twoPartIgnoreList:
        if assertion.find(part1) != -1 and assertion.find(part2) != -1:
            return True
    return False


simpleIgnoreList = []
twoPartIgnoreList = []
getIgnores()
#print "detect_assertions is ready (ignoring %d strings without filenames and %d strings with filenames)" % (len(simpleIgnoreList), len(twoPartIgnoreList))

# For use by af_timed_run
def amiss(logPrefix):
    currentFile = file(logPrefix + "-err", "r")
    return fs(currentFile)

# For standalone use
if __name__ == "__main__":
    currentFile = file(sys.argv[1], "r")
    fs(currentFile)

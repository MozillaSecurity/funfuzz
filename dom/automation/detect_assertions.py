#!/usr/bin/env python

import platform

def amiss(logPrefix):
    global ignoreList
    foundSomething = False

    currentFile = file(logPrefix + "-err", "r")
    
    # map from (assertion message) to (true, if seen in the current file)
    seenInCurrentFile = {}

    for line in currentFile:
        line = line.strip("\x07").rstrip("\n")
        if (line.startswith("###!!!") and not (line in seenInCurrentFile)):
            seenInCurrentFile[line] = True
            if not (ignore(line)):
                print line
                foundSomething = True

    currentFile.close()
    
    return foundSomething


def getIgnores():

    global simpleIgnoreList
    ignoreFile = open("known_assertions.txt", "r")

    for line in ignoreFile:
        line = line.strip()
        if ((len(line) > 0) and not line.startswith("#")):
            mpi = line.find(", file ")  # assertions use this format
            if (mpi == -1):
                mpi = line.find(": file ")  # aborts use this format
            if (mpi == -1):
                simpleIgnoreList.append(line)
            else:
                twoPartIgnoreList.append((line[:mpi+7], localSlashes(line[mpi+7:])))
                
def localSlashes(s):
    if platform.system() in ('Windows', 'Microsoft'):
        return s.replace("\\", "/")
    return s

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

#!/usr/bin/env python

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

    global ignoreList
    ignoreFile = open("known_assertions.txt", "r")

    for line in ignoreFile:
        line = line.strip()
        if ((len(line) > 0) and not line.startswith("#")):
            ignoreList.append(line)

def ignore(assertion):

    global ignoreList
    for ig in ignoreList:
        if (assertion.find(ig) != -1):
            return True
    return False


ignoreList = []
getIgnores()
# print "detect_assertions is ready (ignoring %d assertions)" % len(ignoreList)

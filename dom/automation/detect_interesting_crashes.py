#!/usr/bin/env python

import os

def amiss(logPrefix):
    global ignoreList
    igmatch = []
    fn = logPrefix + "-crash"
    
    if os.path.exists(fn):
        currentFile = file(fn, "r")
        for line in currentFile:
            for ig in ignoreList:
                if line.find(ig) != -1:
                    igmatch.append(ig)
        currentFile.close()
        
        if len(igmatch) == 0:
            # Would be great to print [@ nsFoo::Bar] in addition to the filename
            print "Unknown crash: " + fn
            return True
        else:
            print "Known crash: " + ", ".join(igmatch)
            return False
    else:
        print "Unknown crash (crash log is missing)"
        return True


def getIgnores():
    global ignoreList
    ignoreFile = open("known_crashes.txt", "r")
    for line in ignoreFile:
        line = line.strip()
        if ((len(line) > 0) and not line.startswith("#")):
            ignoreList.append(line)

def ignore(assertion):
    global ignoreList
    for ig in ignoreList:
        if assertion.find(ig) != -1:
            return True
    return False


ignoreList = []
getIgnores()

#print "detect_interesting_crashes is ready (ignoring %d strings)" % (len(ignoreList))

#!/usr/bin/env python -u

import sys, random, time, os
import detect_assertions, detect_leaks, detect_malloc_errors
sys.path.append("../../lithium/")
import ntr



def many_timed_runs(fullURLs):
    
    for iteration in range(0, len(fullURLs)):
        fullURL = fullURLs[iteration]
        # print "URL: " + URL
        logPrefix = tempDir + os.sep + "w" + str(iteration)
        (sta, msg, elapsedtime) = ntr.timed_run(sys.argv[3:] + [fullURL], int(sys.argv[1]), logPrefix)
        
        print "%s: %s (%.1f seconds)" % (logPrefix, msg, elapsedtime)
        
        if sta == ntr.CRASHED:
            print "Approximate crash time: " + time.asctime()

        amissAssert = detect_assertions.amiss(logPrefix)
        amissLeak = detect_leaks.amiss(logPrefix)
        amissMalloc = detect_malloc_errors.amiss(logPrefix)
        
        if ((sta == ntr.CRASHED) or (sta == ntr.ABNORMAL) or amissAssert or amissLeak or amissMalloc):
            print fullURL
            for line in file(logPrefix + "-out"):
                if line.startswith("Chosen"):
                    print line
            print ""
            print ""
        else:
            os.remove(logPrefix + "-out")
            os.remove(logPrefix + "-err")
             

def getURLs():
    URLs = []
    fullURLs = []
    
    urlfile = open(sys.argv[2], "r")
    for line in urlfile:
        if (not line.startswith("#") and len(line) > 2):
            URLs.append(line.rstrip())
            
    plan = file(tempDir + os.sep + "wplan", 'w')

    for iteration in range(0, 100000):
        metaSeed = random.randint(1, 10000)
        metaPer = random.randint(0, 15) * random.randint(0, 15) + 5
        u = random.choice(URLs) + "#squarefree-af!fuzzer-combined.js!" + str(metaSeed) + ",0," + str(metaPer) + ",10,3000,0"
        fullURLs.append(u)
        plan.write(tempDir + os.sep + "w" + str(iteration) + " = " + u + "\n")
    
    plan.close()
    
    return fullURLs


def createTempDir():
    global tempDir
    i = 1
    while 1:
        tempDir = "wtmp" + str(i)
        if not os.path.exists(tempDir):
            os.mkdir(tempDir)
            break
        i += 1




if len(sys.argv) >= 4:
    createTempDir()
    many_timed_runs(getURLs())
else:
    print "Not enough command-line arguments"
    print "Usage: ./af_timed_run.py timeout urllist firefoxpath [firefoxargs ...]"


#!/usr/bin/env python -u

import sys, random, time, os
import detect_assertions, detect_leaks, detect_malloc_errors, detect_interesting_crashes
sys.path.append("../../lithium/")
import ntr
import randomURL


urlListFilename = sys.argv[2]
maxIterations = 100000
yummy = (urlListFilename == "urls-random")


def many_timed_runs(fullURLs):
    
    for iteration in range(0, maxIterations):

        if yummy:
            fullURL = randomURL.randomURL() + randomHash()
        else:
            fullURL = fullURLs[iteration]

        logPrefix = tempDir + os.sep + "w" + str(iteration)

        c = file(logPrefix + "-url", "w")
        c.write(fullURL)
        c.close()

        (sta, msg, elapsedtime) = ntr.timed_run(sys.argv[3:] + [fullURL], int(sys.argv[1]), logPrefix)
        
        amissAssert = detect_assertions.amiss(logPrefix, False)
        amissLeak = detect_leaks.amiss(logPrefix)
        amissMalloc = detect_malloc_errors.amiss(logPrefix)
        amissInterestingCrash = False if (sta != ntr.CRASHED) else detect_interesting_crashes.amiss(logPrefix, False, msg)

        amiss = ((sta == ntr.ABNORMAL) or amissAssert or amissLeak or amissMalloc or amissInterestingCrash)
        amissStr = "" if not amiss else "*"
        print "%s: %s%s (%.1f seconds)" % (logPrefix, amissStr, msg, elapsedtime)

        if amiss:
            print fullURL
            for line in file(logPrefix + "-out"):
                if line.startswith("Chosen"):
                    print line
            print ""
            print ""
        
        if sta == ntr.NORMAL and not amiss:
            os.remove(logPrefix + "-out")
            os.remove(logPrefix + "-err")
            os.remove(logPrefix + "-url")


def getURLs():
    URLs = []
    fullURLs = []
    
    urlfile = open(urlListFilename, "r")
    for line in urlfile:
        if (not line.startswith("#") and len(line) > 2):
            URLs.append(line.rstrip())
            
    plan = file(tempDir + os.sep + "wplan", 'w')

    for iteration in range(0, maxIterations):
        u = random.choice(URLs) + randomHash()
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

def randomHash():
    metaSeed = random.randint(1, 10000)
    metaPer = random.randint(0, 15) * random.randint(0, 15) + 5
    return "#squarefree-af!fuzzer-combined.js!" + str(metaSeed) + ",0," + str(metaPer) + ",10,3000,0"

if len(sys.argv) >= 4:
    createTempDir()
    if yummy: # hacky
        many_timed_runs(None)
    else:
        many_timed_runs(getURLs())
else:
    print "Not enough command-line arguments"
    print "Usage: ./af_timed_run.py timeout urllist firefoxpath [firefoxargs ...]"

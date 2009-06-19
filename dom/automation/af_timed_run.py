#!/usr/bin/env python

import sys, random, time, os
import domunhappy
import randomURL

timeout = int(sys.argv[1])
urlListFilename = sys.argv[2]
knownPath = sys.argv[3]
maxIterations = 300000
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

        runThis = sys.argv[4:] + [fullURL]
        level = domunhappy.level(runThis, timeout, logPrefix)

        if level > domunhappy.DOM_TIMED_OUT:
            print fullURL
            for line in file(logPrefix + "-out"):
                if line.startswith("Chosen"):
                    print line
            # XXX run Lithium
            print ""
        else:
            os.remove(logPrefix + "-out")
            os.remove(logPrefix + "-err")
            if (os.path.exists(logPrefix + "-crash")):
                os.remove(logPrefix + "-crash")
            if (os.path.exists(logPrefix + "-core")):
                os.remove(logPrefix + "-core")


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
        # To avoid race conditions, we use try/except instead of exists/create
        # Hopefully we don't get any errors other than "File exists" :)
        try:
            os.mkdir(tempDir)
            break
        except OSError, e:
            i += 1
    print tempDir + os.sep

def randomHash():
    metaSeed = random.randint(1, 10000)
    metaPer = random.randint(0, 15) * random.randint(0, 15) + 5
    return "#squarefree-af!fuzzer-combined.js!" + str(metaSeed) + ",0," + str(metaPer) + ",10,3000,0"

if len(sys.argv) >= 5:
    domunhappy.initWithKnownPath(knownPath)
    createTempDir()
    if yummy: # hacky
        many_timed_runs(None)
    else:
        many_timed_runs(getURLs())
else:
    print "Not enough command-line arguments"
    print "Usage: ./af_timed_run.py timeout urllist knownpath firefoxpath [firefoxargs ...]"

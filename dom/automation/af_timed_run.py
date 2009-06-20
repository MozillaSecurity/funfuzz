#!/usr/bin/env python

import sys, random, time, os, subprocess
import domunhappy
import randomURL

p0 = os.path.dirname(sys.argv[0])
emptiesDir = os.path.abspath(os.path.join(p0, "..", "empties"))
fuzzersDir = os.path.abspath(os.path.join(p0, "..", "fuzzers"))
lithiumpy = ["python", "-u", os.path.join(p0, "..", "..", "lithium", "lithium.py")]
domunhappypy = os.path.join(p0, "domunhappy.py")

timeout = int(sys.argv[1])
urlListFilename = sys.argv[2]
knownPath = sys.argv[3]
browser = sys.argv[4:] # e.g. 'firefox-bin -P fuzz1', should be able to accept a testcase filename appended
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

        runThis = browser + [fullURL]
        level = domunhappy.level(runThis, timeout, logPrefix)

        if level > domunhappy.DOM_TIMED_OUT:
            print fullURL
            for line in file(logPrefix + "-out"):
                if line.startswith("Chosen"):
                    print line
            wheeLith(level, logPrefix)
            print ""
        else:
            os.remove(logPrefix + "-out")
            os.remove(logPrefix + "-err")
            if (os.path.exists(logPrefix + "-crash")):
                os.remove(logPrefix + "-crash")
            if (os.path.exists(logPrefix + "-core")):
                os.remove(logPrefix + "-core")

def wheeLith(level, logPrefix):
    contentTypes = linesWith(open(logPrefix + "-out"), "XA Content type: ")
    contentType = afterColon(contentTypes[0]) if len(contentTypes) > 0 else "text/html"

    extDict = {
        'text/html': 'html',
        'application/xhtml+xml': 'xhtml',
        'image/svg+xml': 'svg',
        'application/vnd.mozilla.xul+xml': 'xul'
    }
    
    if contentType not in extDict:
        # In particular, 'text/xml' is tricky... we'd want to know the xmlns of the root, and steal its contents but use .xml, perhaps
        print "af_timed_run does not know what to do with content type " + repr(contentType) + " :("
        return
        
    extension = extDict[contentType]

    [wbefore, wafter] = fuzzDice(open(os.path.join(emptiesDir, "a." + extension)))

    possibleDoctype = []
    if contentType == "text/html":
        docTypes = linesWith(open(logPrefix + "-out"), "XA Doctype: ")
        if len(docTypes) > 0:
            possibleDoctype = [afterColon(docTypes[0]) + "\n"]
            
    fuzzjs = open(os.path.join(fuzzersDir, "fuzz.js")).readlines()
    fuzzstartjs = open(os.path.join(fuzzersDir, "fuzz-start.js")).readlines()
    [jbefore, jafter] = fuzzSplice(open(os.path.join(fuzzersDir, "fuzzer-combined.js")))
    fuzzlines = linesWith(open(logPrefix + "-out"), "FRC")
    quittage = [
      "// DDEND\n",
      "fuzzCommands.push({origCount: 9999, rest: true});\n",
      "fuzzCommands.push({origCount: 9999, fun: goQuitApplication});\n"
    ]
    linesToWrite = possibleDoctype + wbefore + jbefore + fuzzlines + quittage + jafter + fuzzjs + fuzzstartjs + wafter
    
    oFN = logPrefix + "-splice-orig." + extension
    rFN = logPrefix + "-splice-reduced." + extension
    writeLinesToFile(linesToWrite, oFN)
    writeLinesToFile(linesToWrite, rFN)
    
    # Run Lithium as a subprocess: reduce to the smallest file that has at least the same unhappiness level
    lithArgs = [domunhappypy, str(level), str(timeout), knownPath] + browser + [rFN]
    print "af_timed_run is running Lithium..."
    print repr(lithiumpy + lithArgs)
    subprocess.call(lithiumpy + lithArgs, stdout=open(logPrefix + "-lith1", "w"))
    print "Done running Lithium"



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




def fuzzSplice(file):
    '''Returns the lines of a file, minus the ones between the two lines containing SPLICE'''
    before = []
    after = []
    for line in file:
        before.append(line)
        if line.find("SPLICE") != -1:
            break
    for line in file:
        if line.find("SPLICE") != -1:
            after.append(line)
            break
    for line in file:
        after.append(line)
    file.close()
    return [before, after]

def fuzzDice(file):
    '''Returns the lines of the file, except for the one line containing DICE'''
    before = []
    after = []
    for line in file:
        if line.find("DICE") != -1:
            break
        before.append(line)
    for line in file:
        after.append(line)
    file.close()
    return [before, after]


def linesWith(file, searchFor):
    '''Returns the lines from a file that contain a given string'''
    matchingLines = []
    for line in file:
        if line.find(searchFor) != -1:
            matchingLines.append(line)
    file.close()
    return matchingLines

def writeLinesToFile(lines, filename):
      f = open(filename, "w")
      f.writelines(lines)
      f.close()

def afterColon(s):
    (head, sep, tail) = s.partition(": ")
    return tail.strip()



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

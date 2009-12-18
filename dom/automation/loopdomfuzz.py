#!/usr/bin/env python

from __future__ import with_statement
import sys, random, time, os, subprocess, datetime, urllib
import rundomfuzz
import randomURL

if len(sys.argv) != 2:
   print "Usage: ./loopdomfuzz.py firefox-objdir"
   sys.exit(2)

p0 = os.path.dirname(sys.argv[0])
emptiesDir = os.path.abspath(os.path.join(p0, "..", "empties"))
fuzzersDir = os.path.abspath(os.path.join(p0, "..", "fuzzers"))
lithiumpy = ["python", "-u", os.path.join(p0, "..", "..", "lithium", "lithium.py")]
rundomfuzzpy = os.path.join(p0, "rundomfuzz.py")

urlListFilename = "urls-reftests" # XXX make this "--urls=..." somehow
fuzzerJS = "fuzzer-combined.js" # XXX make this "--fuzzerjs=" somehow, needed for fuzzer-combined-smart-rjs.js
browserObjDir = os.path.abspath(sys.argv[1])
maxIterations = 300000
yummy = (urlListFilename == "urls-random")


def many_timed_runs(fullURLs):

    for iteration in range(0, maxIterations):

        if yummy:
            fullURL = randomURL.randomURL() + randomHash()
        else:
            fullURL = fullURLs[iteration]

        logPrefix = os.path.join(tempDir, "q" + str(iteration))
        now = datetime.datetime.isoformat(datetime.datetime.now(), " ")
        print "%%% " + now + " starting q" + str(iteration) + ": " + fullURL
        level, lines = rundomfuzz.levelAndLines(browserObjDir, fullURL, logPrefix=logPrefix)

        if level > rundomfuzz.DOM_TIMED_OUT:
            print "lopdomfuzz.py: will try reducing from " + fullURL
            lithSuccess = wheeLith(level, lines, logPrefix)
            if not lithSuccess:
                print "%%% Failed to reduce using Lithium"
                level2, lines2 = rundomfuzz.levelAndLines(browserObjDir, fullURL, logPrefix=None)
                if level2 > rundomfuzz.DOM_TIMED_OUT:
                    print "%%% Yet it is reproducible"
                    reproOnlyFile = open(logPrefix + "-repro-only.txt", "w")
                    reproOnlyFile.write("I was able to reproduce an issue at the same URL, but Lithium was not.\n")
                    reproOnlyFile.write("./rundomfuzz.py " + browserObjDir + " " + fullURL + "\n")
                    reproOnlyFile.close()
                else:
                    print "%%% Not reproducible at all"
                    sorryFile = open(logPrefix + "-sorry.txt", "w")
                    sorryFile.write("I wasn't even able to reproduce with the same URL.\n")
                    sorryFile.write("./rundomfuzz.py " + browserObjDir + " " + fullURL + "\n")
                    sorryFile.close()

            print ""

# Stuffs "lines" into a fresh file, then runs Lithium to reduce that file.
# Returns True if Lithium was able to reproduce (and reduce).
def wheeLith(level, lines, logPrefix):
    contentTypes = linesWith(lines, "FRCX Content type: ")
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
        return False
        
    extension = extDict[contentType]

    [wbefore, wafter] = fuzzDice(open(os.path.join(emptiesDir, "a." + extension)))

    possibleDoctype = []
    if contentType == "text/html":
        docTypes = linesWith(lines, "FRCX Doctype: ")
        if len(docTypes) > 0:
            possibleDoctype = [afterColon(docTypes[0]) + "\n"]
            
    fuzzjs = open(os.path.join(fuzzersDir, "fuzz.js")).readlines()
    fuzzstartjs = open(os.path.join(fuzzersDir, "fuzz-start.js")).readlines()
    [jbefore, jafter] = fuzzSplice(open(os.path.join(fuzzersDir, fuzzerJS)))
    fuzzlines = linesWith(lines, "FRCA")
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
    lithtmp = logPrefix + "-lith1-tmp"
    os.mkdir(lithtmp)
    lithArgs = ["--tempdir=" + lithtmp, rundomfuzzpy, str(level), browserObjDir, rFN]
    print "af_timed_run is running Lithium..."
    print repr(lithiumpy + lithArgs)
    lithlogfn = logPrefix + "-lith1-out"
    subprocess.call(lithiumpy + lithArgs, stdout=open(lithlogfn, "w"))
    print "Done running Lithium"

    # Rename the "-reduced" file to indicate how large it is.
    rFN2 = None
    with file(lithlogfn) as f:
      inLithSummary = False
      for line in f:
        if inLithSummary:
          if line.startswith("  Final size:"):
            rFN2 = logPrefix + "-splice-reduced-" + line[14:].rstrip().replace(" ", "-") + "." + extension
        if line.rstrip() == "=== LITHIUM SUMMARY ===":
          inLithSummary = True
    if rFN2:
      os.rename(rFN, rFN2)
      return True
    else:
      os.remove(rFN)
      return False



def getURLs():
    URLs = []
    fullURLs = []

    urlfile = open(urlListFilename, "r")
    for line in urlfile:
        if (not line.startswith("#") and len(line) > 2):
            if urlListFilename == "urls-reftests":
                # This has to be a file: URL (rather than just a path) so the "#" will be interpreted as a hash-part
                localPath = os.path.join(browserObjDir, "..", line.rstrip()) # XXX will be different for packaged builds
                URLs.append("file://" + urllib.pathname2url(localPath))
            else:
                URLs.append(line.rstrip())
            
    #plan = file(tempDir + os.sep + "wplan", 'w')

    for iteration in range(0, maxIterations):
        u = random.choice(URLs) + randomHash()
        fullURLs.append(u)
        #plan.write(tempDir + os.sep + "w" + str(iteration) + " = " + u + "\n")
    
    #plan.close()
    
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
    return "#squarefree-af!" + fuzzerJS + "!" + str(metaSeed) + ",0," + str(metaPer) + ",10,3000,0"




def fuzzSplice(file):
    '''Returns the lines of a file, minus the ones between the two lines containing SPLICE and between the two lines containing IDLINFO'''
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
        if line.find("IDLINFO") != -1:
            break
    for line in file:
        if line.find("IDLINFO") != -1:
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


def linesWith(lines, searchFor):
    '''Returns the lines from an array that contain a given string'''
    matchingLines = []
    for line in lines:
        if line.find(searchFor) != -1:
            matchingLines.append(line)
    return matchingLines

def writeLinesToFile(lines, filename):
      f = open(filename, "w")
      f.writelines(lines)
      f.close()

def afterColon(s):
    (head, sep, tail) = s.partition(": ")
    return tail.strip()



if len(sys.argv) >= 1:
    createTempDir()
    if yummy: # hacky
        many_timed_runs(None)
    else:
        many_timed_runs(getURLs())
else:
    print "Not enough command-line arguments"
    print "Usage: loopdomfuzz.py fxobjdir [options for automation.py]"

#!/usr/bin/env python

from __future__ import with_statement
import sys, random, time, os, subprocess, datetime, urllib
import rundomfuzz

p0 = os.path.dirname(__file__)
emptiesDir = os.path.abspath(os.path.join(p0, "..", "empties"))
fuzzersDir = os.path.abspath(os.path.join(p0, "..", "fuzzers"))
lithiumpy = ["python", "-u", os.path.join(p0, "..", "..", "lithium", "lithium.py")]
rundomfuzzpy = os.path.join(p0, "rundomfuzz.py")

urlListFilename = "urls-reftests" # XXX make this "--urls=..." somehow
fuzzerJS = "fuzzer-combined.js" # XXX make this "--fuzzerjs=" somehow, needed for fuzzer-combined-smart-rjs.js

tempDir = None

maxIterations = 300000

# If targetTime is None, this loops forever.
# If targetTime is a number, tries not to run for more than targetTime seconds.
#   But if it finds a bug in the browser, it may run for less time, or even for 50% more time.
def many_timed_runs(targetTime, args):
    createTempDir()
    startTime = time.time()

    levelAndLines, options = rundomfuzz.rdfInit(args)
    browserDir = options.browserDir

    reftestFilesDir = rundomfuzz.FigureOutDirs(browserDir).reftestFilesDir
    urls = getURLs(os.path.abspath(reftestFilesDir))

    for iteration in range(0, maxIterations):
        if targetTime and time.time() > startTime + targetTime:
            print "Out of time!"
            if len(os.listdir(tempDir)) == 0:
                os.rmdir(tempDir)
            return (None, HAPPY, None)

        url = urls[iteration]

        logPrefix = os.path.join(tempDir, "q" + str(iteration))
        now = datetime.datetime.isoformat(datetime.datetime.now(), " ")
        print "%%% " + now + " starting q" + str(iteration) + ": " + url
        level, lines = levelAndLines(url, logPrefix=logPrefix)

        if level > rundomfuzz.DOM_FINE:
            print "loopdomfuzz.py: will try reducing from " + url
            rFN = createReproFile(lines, logPrefix)
            extraRDFArgs = ["--valgrind"] if options.valgrind else []
            lithArgs = [rundomfuzzpy] + extraRDFArgs + ["-m%d" % level, browserDir, rFN]
            (lithlog, lithresult, lithdetails) = runLithium(lithArgs, logPrefix, targetTime and targetTime//2, "1")
            if lithresult == LITH_NO_REPRO:
                os.remove(rFN)
                print "%%% Lithium can't reproduce. One more shot to see if it's reproducible at all."
                level2, lines2 = levelAndLines(url, logPrefix=logPrefix+"-retry")
                if level2 > rundomfuzz.DOM_FINE:
                    print "%%% Lithium can't reproduce, but I can!"
                    reproOnlyFile = open(logPrefix + "-repro-only.txt", "w")
                    reproOnlyFile.write("I was able to reproduce an issue at the same URL, but Lithium was not.\n\n")
                    reproOnlyFile.write("./rundomfuzz.py " + browserDir + " " + url + "\n")
                    reproOnlyFile.close()
                    lithresult = NO_REPRO_EXCEPT_BY_URL
                else:
                    print "%%% Lithium can't reproduce, and neither can I."
                    sorryFile = open(logPrefix + "-sorry.txt", "w")
                    sorryFile.write("I wasn't even able to reproduce with the same URL.\n\n")
                    sorryFile.write("./rundomfuzz.py " + browserDir + " " + url + "\n")
                    sorryFile.close()
                    lithresult = NO_REPRO_AT_ALL
            print ""
            if targetTime:
                return (lithlog, lithresult, lithdetails)

# Stuffs "lines" into a fresh file, which Lithium should be able to reduce.
# Returns the name of the repro file.
def createReproFile(lines, logPrefix):
    contentTypes = linesWith(lines, "FRCX Content type: ")
    contentType = afterColon(contentTypes[0]) if len(contentTypes) > 0 else "text/html"

    extDict = {
        'text/html': 'html',
        'application/xhtml+xml': 'xhtml',
        'image/svg+xml': 'svg',
        'application/vnd.mozilla.xul+xml': 'xul',
        # 'text/xml' is tricky.  We'd want to know the xmlns of the root, and steal its contents but use .xml.
        # But treating it as xhtml is better than doing nothing, for now.
        'text/xml': 'xhtml' 
    }
    
    if contentType in extDict:
        extension = extDict[contentType]
    else:
        print "loopdomfuzz is not sure what to do with content type " + repr(contentType) + " :("
        extension = "xhtml"

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
    
    return rFN

# status returns for runLithium and many_timed_runs
(HAPPY, NO_REPRO_AT_ALL, NO_REPRO_EXCEPT_BY_URL, LITH_NO_REPRO, LITH_FINISHED, LITH_RETESTED_STILL_INTERESTING, LITH_PLEASE_CONTINUE, LITH_BUSTED) = range(8)


def runLithium(lithArgs, logPrefix, targetTime, fileTag):
    """
      Run Lithium as a subprocess: reduce to the smallest file that has at least the same unhappiness level.
      Returns a tuple of (lithlogfn, LITH_*, details).
    """
    if targetTime:
      # loopdomfuzz.py is being used by bot.py
      lithArgs = ["--maxruntime=" + str(targetTime)] + lithArgs
      lithlogfn = logPrefix.split(os.sep)[0] + os.sep + "lith" + fileTag + "-out"
      # should probably use mkdtemp for the tempdir in this case
    else:
      # loopdomfuzz.py is being run standalone
      lithtmp = logPrefix + "-lith" + fileTag + "-tmp"
      os.mkdir(lithtmp)
      lithArgs = ["--tempdir=" + lithtmp] + lithArgs
      lithlogfn = logPrefix + "-lith" + fileTag + "-out"
    print "Preparing to run Lithium, log file " + lithlogfn
    print " ".join(lithiumpy + lithArgs)
    subprocess.call(lithiumpy + lithArgs, stdout=open(lithlogfn, "w"), stderr=subprocess.STDOUT)
    print "Done running Lithium"
    with file(lithlogfn) as f:
      for line in f:
        if line.startswith("Lithium result"):
          print line.rstrip()
        if line.startswith("Lithium result: interesting"):
          return (lithlogfn, LITH_RETESTED_STILL_INTERESTING, None)
        elif line.startswith("Lithium result: succeeded, reduced to: "):
          reducedTo = line[len("Lithium result: succeeded, reduced to: "):].rstrip() # e.g. "4 lines"
          return (lithlogfn, LITH_FINISHED, reducedTo)
        elif line.startswith("Lithium result: not interesting") or line.startswith("Lithium result: the original testcase is not"):
          return (lithlogfn, LITH_NO_REPRO, None)
        elif line.startswith("Lithium result: please continue using: "):
          lithiumHint = line[len("Lithium result: please continue using: "):].rstrip()
          return (lithlogfn, LITH_PLEASE_CONTINUE, lithiumHint)
      else:
        return (lithlogfn, LITH_BUSTED, None)


def getURLs(reftestFilesDir):
    URLs = []
    fullURLs = []

    urlfile = open(os.path.join(p0, urlListFilename), "r")
    for line in urlfile:
        if (not line.startswith("#") and len(line) > 2):
            if urlListFilename == "urls-reftests":
                localPath = os.path.join(reftestFilesDir, line.rstrip())
                # This has to be a file: URL (rather than just a path) so the "#" will be interpreted as a hash-part
                URLs.append("file:" + urllib.pathname2url(localPath))
            else:
                URLs.append(line.rstrip())
            
    for iteration in range(0, maxIterations):
        u = random.choice(URLs) + randomHash()
        fullURLs.append(u)
    
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
    return "#squarefree-af," + fuzzerJS + "," + str(metaSeed) + ",0," + str(metaPer) + ",10,3000,0"




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

if __name__ == "__main__":
    many_timed_runs(None, sys.argv[1:])


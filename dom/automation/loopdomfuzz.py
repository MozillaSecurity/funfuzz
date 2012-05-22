#!/usr/bin/env python

from __future__ import with_statement

import datetime
import os
import random
import shutil
import subprocess
import sys
import time
import urllib

from tempfile import mkdtemp

import domInteresting

p0 = os.path.dirname(os.path.abspath(__file__))
emptiesDir = os.path.abspath(os.path.join(p0, os.pardir, "empties"))
fuzzersDir = os.path.abspath(os.path.join(p0, os.pardir, "fuzzers"))
lithiumpy = ["python", "-u", os.path.join(p0, os.pardir, os.pardir, "lithium", "lithium.py")]
domInterestingpy = os.path.join("fuzzing", "dom", "automation", "domInteresting.py")

path1 = os.path.abspath(os.path.join(p0, os.pardir, os.pardir, 'util'))
sys.path.append(path1)
from subprocesses import shellify

urlListFilename = "urls-reftests" # XXX make this "--urls=..." somehow
fuzzerJS = "fuzzer-combined.js" # XXX make this "--fuzzerjs=" somehow

tempDir = None

maxIterations = 300000

# If targetTime is None, this loops forever.
# If targetTime is a number, tries not to run for more than targetTime seconds.
#   But if it finds a bug in the browser, it may run for less time, or even for 50% more time.
def many_timed_runs(targetTime, args):
    createTempDir()
    startTime = time.time()

    levelAndLines, deleteProfile, options = domInteresting.rdfInit(args)
    try:
        browserDir = options.browserDir

        reftestFilesDir = domInteresting.FigureOutDirs(browserDir).reftestFilesDir
        urls = getURLs(os.path.abspath(reftestFilesDir))
        with open(os.path.join(p0, "bool-prefs.txt")) as f:
            boolPrefNames = filter(lambda s: len(s) and s[0] != "#", f)

        for iteration in xrange(0, maxIterations):
            if targetTime and time.time() > startTime + targetTime:
                print "Out of time!"
                if len(os.listdir(tempDir)) == 0:
                    os.rmdir(tempDir)
                return (None, HAPPY, None)

            url = urls[iteration]
            prefs = map(lambda s: 'user_pref("' + s.strip() + '", ' + random.choice(["true", "false"]) + ');\n', boolPrefNames) + nonBoolPrefs()

            logPrefix = os.path.join(tempDir, "q" + str(iteration))
            now = datetime.datetime.isoformat(datetime.datetime.now(), " ")
            print "%%% " + now + " starting q" + str(iteration) + ": " + url
            level, lines = levelAndLines(url, logPrefix=logPrefix, extraPrefs="\n".join(prefs))

            if level > domInteresting.DOM_FINE:
                print "loopdomfuzz.py: will try reducing from " + url
                rFN = createReproFile(lines, logPrefix)
                writeLinesToFile(prefs, logPrefix + "-prefs.txt") # domInteresting.py will look for this file when invoked by Lithium or directly
                extraRDFArgs = ["--valgrind"] if options.valgrind else []
                lithArgs = [domInterestingpy] + extraRDFArgs + ["-m%d" % level, browserDir, rFN]
                (lithlog, lithresult, lithdetails) = runLithium(lithArgs, logPrefix, targetTime and targetTime//2, "1")
                if lithresult == LITH_NO_REPRO:
                    os.remove(rFN)
                    print "%%% Lithium can't reproduce. One more shot to see if it's reproducible at all."
                    level2, lines2 = levelAndLines(url, logPrefix=logPrefix+"-retry", extraPrefs="\n".join(prefs))
                    if level2 > domInteresting.DOM_FINE:
                        print "%%% Lithium can't reproduce, but I can!"
                        with open(logPrefix + "-repro-only.txt", "w") as reproOnlyFile:
                            reproOnlyFile.write("I was able to reproduce an issue at the same URL, but Lithium was not.\n\n")
                            reproOnlyFile.write(domInterestingpy  + " " + browserDir + " " + url + "\n")
                        lithresult = NO_REPRO_EXCEPT_BY_URL
                    else:
                        print "%%% Lithium can't reproduce, and neither can I."
                        with open(logPrefix + "-sorry.txt", "w") as sorryFile:
                            sorryFile.write("I wasn't even able to reproduce with the same URL.\n\n")
                            sorryFile.write(domInterestingpy  + " " + browserDir + " " + url + "\n")
                        lithresult = NO_REPRO_AT_ALL
                print ""
                if targetTime:
                    return (lithlog, lithresult, lithdetails)
    finally:
        deleteProfile()

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
      "fuzzCommands.push({origCount: 8888, rest: true, timeout: 3000});\n",
      "fuzzCommands.push({origCount: 9999, fun: function() { fuzzPriv.quitApplication(); } });\n"
    ]
    linesToWrite = possibleDoctype + wbefore + jbefore + fuzzlines + quittage + jafter + fuzzjs + fuzzstartjs + wafter

    oFN = logPrefix + "-splice-orig." + extension
    rFN = logPrefix + "-splice-reduced." + extension
    writeLinesToFile(linesToWrite, oFN)
    writeLinesToFile(linesToWrite, rFN)
    subprocess.call(["gzip", oFN])

    return rFN

# status returns for runLithium and many_timed_runs
(HAPPY, NO_REPRO_AT_ALL, NO_REPRO_EXCEPT_BY_URL, LITH_NO_REPRO, LITH_FINISHED, LITH_RETESTED_STILL_INTERESTING, LITH_PLEASE_CONTINUE, LITH_BUSTED) = range(8)


def runLithium(lithArgs, logPrefix, targetTime, fileTag):
    """
      Run Lithium as a subprocess: reduce to the smallest file that has at least the same unhappiness level.
      Returns a tuple of (lithlogfn, LITH_*, details).
    """
    deletableLithTemp = None
    if targetTime:
        # loopdomfuzz.py is being used by bot.py
        deletableLithTemp = mkdtemp(prefix="domfuzz-ldf-bot")
        lithArgs = ["--maxruntime=" + str(targetTime), "--tempdir=" + deletableLithTemp] + lithArgs
        lithlogfn = os.path.join(logPrefix, "lith" + fileTag + "-out")
    else:
        # loopdomfuzz.py is being run standalone
        lithtmp = logPrefix + "-lith" + fileTag + "-tmp"
        os.mkdir(lithtmp)
        lithArgs = ["--tempdir=" + lithtmp] + lithArgs
        lithlogfn = logPrefix + "-lith" + fileTag + "-out"
    print "Preparing to run Lithium, log file " + lithlogfn
    print shellify(lithiumpy + lithArgs)
    subprocess.call(lithiumpy + lithArgs, stdout=open(lithlogfn, "w"), stderr=subprocess.STDOUT)
    print "Done running Lithium"
    if deletableLithTemp:
        shutil.rmtree(deletableLithTemp)
    r = readLithiumResult(lithlogfn)
    subprocess.call(["gzip", "-f", lithlogfn])
    return r

def readLithiumResult(lithlogfn):
    with open(lithlogfn) as f:
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

    with open(os.path.join(p0, urlListFilename)) as urlfile:
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
    metaInterval = 2 ** random.randint(0, 12) - 1
    metaPer = random.randint(0, 15) * random.randint(0, 15) + 5 + int(metaInterval / 10)
    metaMax = 3000
    return "#squarefree-af," + fuzzerJS + "," + str(metaSeed) + ",0," + str(metaPer) + "," + str(metaInterval) + "," + str(metaMax) + ",0"

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


def linesWith(lines, searchFor):
    '''Returns the lines from an array that contain a given string'''
    matchingLines = []
    for line in lines:
        if line.find(searchFor) != -1:
            matchingLines.append(line)
    return matchingLines

def writeLinesToFile(lines, filename):
    with open(filename, "w") as f:
        f.writelines(lines)

def afterColon(s):
    (head, sep, tail) = s.partition(": ")
    return tail.strip()

def nonBoolPrefs():
    p = []
    if random.random() > 0.8:
        p += ['user_pref("font.size.inflation.minTwips", 120);\n']
        p += ['user_pref("font.size.inflation.emPerLine", 15);\n']
        p += ['user_pref("font.size.inflation.lineThreshold", ' + str(random.randrange(0, 400)) + ');\n']
        p += ['user_pref("browser.sessionhistory.max_entries", ' + str(random.randrange(2, 10)) + ');\n']
        p += ['user_pref("browser.sessionhistory.max_total_viewers", ' + str(random.randrange(0, 4)) + ');\n']
        p += ['user_pref("bidi.direction", ' + random.choice(["1", "2"]) + ');\n']
        p += ['user_pref("bidi.numeral", ' + random.choice(["0", "1", "2", "3", "4"]) + ');\n']
        p += ['user_pref("browser.display.use_document_fonts", ' + random.choice(["0", "1"]) + ');\n']
        p += ['user_pref("browser.history.maxStateObjectSize", ' + random.choice(["0", "100", "655360", "655360"]) + ');\n']
        p += ['user_pref("browser.sessionstore.interval", ' + random.choice(["100", "1000", "15000"]) + ');\n']
        p += ['user_pref("browser.sessionstore.max_tabs_undo", ' + random.choice(["0", "1", "10"]) + ');\n']
        p += ['user_pref("browser.sessionstore.browser.sessionstore.max_windows_undo", ' + random.choice(["0", "1", "10"]) + ');\n']
        p += ['user_pref("browser.sessionstore.postdata", ' + random.choice(["0", "-1", "1000"]) + ');\n']
        p += ['user_pref("layout.scrollbar.side", ' + random.choice(["0", "1", "2", "3"]) + ');\n']
        p += ['user_pref("permissions.default.image", ' + random.choice(["1", "2", "3"]) + ');\n']
        p += ['user_pref("gfx.font_rendering.harfbuzz.scripts", ' + str(random.randrange(0, 0x80)) + ');\n'] # gfx/thebes/gfxUnicodeProperties.h ShapingType bitfield
        #layout.css.devPixelsPerPx
    if random.random() > 0.9:
        p += ['user_pref("intl.uidirection.en", "rtl");\n']
    return p

if __name__ == "__main__":
    many_timed_runs(None, sys.argv[1:])

#!/usr/bin/env python

from __future__ import with_statement

import datetime
import os
import random
import subprocess
import sys
import time
import urllib

import domInteresting

p0 = os.path.dirname(os.path.abspath(__file__))
emptiesDir = os.path.abspath(os.path.join(p0, os.pardir, "empties"))
fuzzersDir = os.path.abspath(os.path.join(p0, os.pardir, "fuzzers"))
domInterestingpy = os.path.join("fuzzing", "dom", "automation", "domInteresting.py")

path1 = os.path.abspath(os.path.join(p0, os.pardir, os.pardir, 'util'))
sys.path.append(path1)
from subprocesses import shellify, createWtmpDir
from fileManipulation import fuzzDice, fuzzSplice, linesWith, writeLinesToFile
import lithOps

urlListFilename = "urls-reftests" # XXX make this "--urls=..." somehow
fuzzerJS = "fuzzer-combined.js" # XXX make this "--fuzzerjs=" somehow

maxIterations = 300000

# If targetTime is None, this loops forever.
# If targetTime is a number, tries not to run for more than targetTime seconds.
#   But if it finds a bug in the browser, it may run for less time, or even for 50% more time.
def many_timed_runs(targetTime, args):
    tempDir = createWtmpDir(os.getcwdu())
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
                return (None, lithOps.HAPPY, None)

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
                (lithresult, lithdetails) = lithOps.runLithium(lithArgs, logPrefix, targetTime and targetTime//2)
                if lithresult == lithOps.LITH_NO_REPRO:
                    os.remove(rFN)
                    print "%%% Lithium can't reproduce. One more shot to see if it's reproducible at all."
                    level2, lines2 = levelAndLines(url, logPrefix=logPrefix+"-retry", extraPrefs="\n".join(prefs))
                    if level2 > domInteresting.DOM_FINE:
                        print "%%% Lithium can't reproduce, but I can!"
                        with open(logPrefix + "-repro-only.txt", "w") as reproOnlyFile:
                            reproOnlyFile.write("I was able to reproduce an issue at the same URL, but Lithium was not.\n\n")
                            reproOnlyFile.write(domInterestingpy  + " " + browserDir + " " + url + "\n")
                        lithresult = lithOps.NO_REPRO_EXCEPT_BY_URL
                    else:
                        print "%%% Lithium can't reproduce, and neither can I."
                        with open(logPrefix + "-sorry.txt", "w") as sorryFile:
                            sorryFile.write("I wasn't even able to reproduce with the same URL.\n\n")
                            sorryFile.write(domInterestingpy  + " " + browserDir + " " + url + "\n")
                        lithresult = lithOps.NO_REPRO_AT_ALL
                print ""
                if targetTime:
                    return (lithresult, lithdetails)
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

    [wbefore, wafter] = fuzzDice(os.path.join(emptiesDir, "a." + extension))

    possibleDoctype = []
    if contentType == "text/html":
        docTypes = linesWith(lines, "FRCX Doctype: ")
        if len(docTypes) > 0:
            possibleDoctype = [afterColon(docTypes[0]) + "\n"]

    with open(os.path.join(fuzzersDir, "fuzz.js")) as f:
        fuzzjs = f.readlines()
    with open(os.path.join(fuzzersDir, "fuzz-start.js")) as g:
        fuzzstartjs = g.readlines()
    [jbefore, jafter] = fuzzSplice(os.path.join(fuzzersDir, fuzzerJS))
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

def randomHash():
    metaSeed = random.randint(1, 10000)
    metaInterval = 2 ** random.randint(0, 12) - 1
    metaPer = random.randint(0, 15) * random.randint(0, 15) + 5 + int(metaInterval / 10)
    metaMax = 3000
    return "#squarefree-af," + fuzzerJS + "," + str(metaSeed) + ",0," + str(metaPer) + "," + str(metaInterval) + "," + str(metaMax) + ",0"

def afterColon(s):
    (head, sep, tail) = s.partition(": ")
    return tail.strip()

def nonBoolPrefs():
    p = []
    if random.random() > 0.2:
        p += ['user_pref("ui.caretBlinkTime", -1);\n']
    if random.random() > 0.8:
        p += ['user_pref("font.size.inflation.minTwips", 120);\n']
    if random.random() > 0.8:
        p += ['user_pref("font.size.inflation.emPerLine", 15);\n']
    if random.random() > 0.8:
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
        p += ['user_pref("accessibility.force_disabled", ' + random.choice(["-1", "0", "1"]) + ');\n']
        p += ['user_pref("gfx.font_rendering.harfbuzz.scripts", ' + str(random.randrange(0, 0x80)) + ');\n'] # gfx/thebes/gfxUnicodeProperties.h ShapingType bitfield
        #layout.css.devPixelsPerPx
    if random.random() > 0.9:
        p += ['user_pref("intl.uidirection.en", "rtl");\n']
    return p

if __name__ == "__main__":
    many_timed_runs(None, sys.argv[1:])

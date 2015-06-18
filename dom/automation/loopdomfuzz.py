#!/usr/bin/env python

import datetime
import os
import platform
import random
import subprocess
import sys
import time
import urllib

import domInteresting
import randomPrefs

p0 = os.path.dirname(os.path.abspath(__file__))
fuzzingDomDir = os.path.abspath(os.path.join(p0, os.pardir))
emptiesDir = os.path.abspath(os.path.join(fuzzingDomDir, "empties"))
domInterestingpy = os.path.join("fuzzing", "dom", "automation", "domInteresting.py")

path1 = os.path.abspath(os.path.join(p0, os.pardir, os.pardir, 'util'))
sys.path.append(path1)
import subprocesses as sps
from fileManipulation import fuzzDice, fuzzSplice, linesStartingWith, writeLinesToFile
import lithOps
import linkJS

urlListFilename = "urls-reftests"  # XXX make this "--urls=..." somehow


def linkFuzzer(target_fn):
    file_list_fn = os.path.join(fuzzingDomDir, "fuzzer", "files-to-link.txt")
    source_base = os.path.join(fuzzingDomDir, "fuzzer")
    linkJS.linkJS(target_fn, file_list_fn, source_base)


# If targetTime is None, this loops forever.
# If targetTime is a number, tries not to run for more than targetTime seconds.
#   But if it finds a bug in the browser, it may run for less time, or even for 50% more time.
def many_timed_runs(targetTime, tempDir, args, quiet=True):
    startTime = time.time()
    iteration = 0

    fuzzerJS = os.path.abspath(os.path.join(tempDir, "fuzzer-combined.js"))
    linkFuzzer(fuzzerJS)
    print fuzzerJS
    os.environ["DOM_FUZZER_SCRIPT"] = fuzzerJS

    levelAndLines, options = domInteresting.rdfInit(args)
    browserDir = options.browserDir

    reftestFilesDir = domInteresting.FigureOutDirs(browserDir).reftestFilesDir
    reftestURLs = getURLs(os.path.abspath(reftestFilesDir))

    while True:
        if targetTime and time.time() > startTime + targetTime:
            print "Out of time!"
            os.remove(fuzzerJS)
            if len(os.listdir(tempDir)) == 0:
                os.rmdir(tempDir)
            return (lithOps.HAPPY, None)

        iteration += 1

        url = options.argURL or (random.choice(reftestURLs) + randomHash())
        extraPrefs = randomPrefs.randomPrefs()

        logPrefix = os.path.join(tempDir, "q" + str(iteration))
        now = datetime.datetime.isoformat(datetime.datetime.now(), " ")
        print "%%% " + now + " starting q" + str(iteration) + ": " + url
        level, lines = levelAndLines(url, logPrefix=logPrefix, extraPrefs=extraPrefs, quiet=quiet)

        if level > domInteresting.DOM_FINE:
            print "loopdomfuzz.py: will try reducing from " + url
            rFN = createReproFile(fuzzerJS, extraPrefs, lines, logPrefix)
            if platform.system() == "Windows":
                rFN = rFN.replace("/", "\\")  # Ensure both Lithium and Firefox understand the filename
            extraRDFArgs = ["--valgrind"] if options.valgrind else []
            lithArgs = [domInterestingpy] + extraRDFArgs + ["-m%d" % level, browserDir, rFN]
            (lithresult, lithdetails) = lithOps.runLithium(lithArgs, logPrefix, targetTime and targetTime//2)
            if lithresult == lithOps.LITH_NO_REPRO:
                os.remove(rFN)
                print "%%% Lithium can't reproduce. One more shot to see if it's reproducible at all."
                level2, _ = levelAndLines(url, logPrefix=logPrefix+"-retry", extraPrefs=extraPrefs)
                if level2 > domInteresting.DOM_FINE:
                    print "%%% Lithium can't reproduce, but I can!"
                    with open(logPrefix + "-repro-only.txt", "w") as reproOnlyFile:
                        reproOnlyFile.write("I was able to reproduce an issue at the same URL, but Lithium was not.\n\n")
                        reproOnlyFile.write(domInterestingpy + " " + browserDir + " " + url + "\n")
                    lithresult = lithOps.NO_REPRO_EXCEPT_BY_URL
                else:
                    print "%%% Lithium can't reproduce, and neither can I."
                    with open(logPrefix + "-sorry.txt", "w") as sorryFile:
                        sorryFile.write("I wasn't even able to reproduce with the same URL.\n\n")
                        sorryFile.write(domInterestingpy + " " + browserDir + " " + url + "\n")
                    lithresult = lithOps.NO_REPRO_AT_ALL
            print ""
            if targetTime:
                return (lithresult, lithdetails)

        if options.argURL:
            break


# Stuffs "lines" into a fresh file, which Lithium should be able to reduce.
# Returns the name of the repro file.
def createReproFile(fuzzerJS, extraPrefs, lines, logPrefix):
    contentTypes = linesStartingWith(lines, "FRCX Content type: ")
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
        docTypes = linesStartingWith(lines, "FRCX Doctype: ")
        if len(docTypes) > 0:
            possibleDoctype = [afterColon(docTypes[0]) + "\n"]

    [jbefore, jafter] = fuzzSplice(fuzzerJS)
    fuzzlines = linesStartingWith(lines, "  /*FRCA")
    if len(fuzzlines) < 3:
        fuzzlines = [
            "// Startup crash?\n",
            "var fuzzSettings = [42,0,42,42,3000,0];\n",
            "var fuzzCommands = [];\n",
            "// DDBEGIN\n"
        ]
    quittage = [
        extraPrefs,
        "// DDEND\n",
        "fuzzCommands.push({origCount: 8888, rest: true, timeout: 3000});\n",
        "fuzzCommands.push({origCount: 9999, fun: function() { fuzzPriv.quitApplication(); } });\n"
        "\n",
        "function user_pref() { /* Allow randomPrefs.py to parse user_pref lines from this file */ }\n",
    ]
    linesToWrite = possibleDoctype + wbefore + jbefore + fuzzlines + quittage + jafter + wafter

    oFN = logPrefix + "-splice-orig." + extension
    rFN = logPrefix + "-splice-reduced." + extension
    writeLinesToFile(linesToWrite, oFN)
    writeLinesToFile(linesToWrite, rFN)
    subprocess.call(["gzip", oFN])

    return rFN


def getURLs(reftestFilesDir):
    URLs = []

    with open(os.path.join(p0, urlListFilename)) as urlfile:
        for line in urlfile:
            if not line.startswith("#") and len(line) > 2:
                if urlListFilename == "urls-reftests":
                    localPath = os.path.join(reftestFilesDir, line.rstrip())
                    # This has to be a file: URL (rather than just a path) so the "#" will be interpreted as a hash-part
                    URLs.append(asFileURL(localPath))
                else:
                    URLs.append(line.rstrip())

    return URLs


def asFileURL(localPath):
    return "file:" + urllib.pathname2url(localPath)


def randomHash():
    metaSeed = random.randint(0, 2**32 - 1)
    metaInterval = 2 ** (random.randint(0, 3) * random.randint(0, 4)) - 1  # Up to 4096ms, but usually faster
    metaPer = random.randint(0, 15) * random.randint(0, 15) + 5 + int(metaInterval / 10)

    # metaMax controls how many [generated js functions] each browser instance will run
    # (but fuzz-finish-auto also enforces a time limit)
    #
    # Want it small:
    #   Deterministic repro from seed (because of time limit) (but how often do we actually repro-from-seed? and this is fixable)
    #   Limit on how much work Lithium has (but how much time do we spend in Lithium, compared to fuzzing?)
    #   Waste less time in huge GCs (especially with fuzzMultiDoc)
    #   Small variations on initial reftests are often the most interesting
    #   Less chance for the fuzzer to tie itself in exponential knots, and hang unexpectedly (e.g. repeated cloneNode)
    #
    # Want it large:
    #   Depth is more important as we scale
    #   Depth is important to fuzzerRandomJS
    #   Waste less time in startup, shutdown
    #   Waste less time parsing breakpad symbol files (!)
    #   Waste less time waiting for hanging testcases (?)

    metaMax = 30000

    return "#fuzz=" + str(metaSeed) + ",0," + str(metaPer) + "," + str(metaInterval) + "," + str(metaMax) + ",0"


def afterColon(s):
    tail = s.partition(": ")[2]
    return tail.strip()


if __name__ == "__main__":
    many_timed_runs(None, sps.createWtmpDir(os.getcwdu()), sys.argv[1:], quiet=False)

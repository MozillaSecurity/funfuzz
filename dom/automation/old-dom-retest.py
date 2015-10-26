#!/usr/bin/env python

import os
import shutil
import tempfile

import domInteresting
import loopdomfuzz
import randomPrefs


retestRoot = "/Users/jruderman/fuzz-results/"
skips = "/Users/jruderman/retest-skips.txt"
buildDir = "build"


def readSkips(filename):
    skips = {}
    if filename:
        with open(filename) as f:
            for line in f:
                jobname = line.split(" ")[0]
                skips[jobname] = True
    return skips


def retestAll():
    '''
    Retest all testcases in retestRoot, starting with the newest,
    without modifying that subtree (because it might be rsync'ed).
    '''

    testcases = []
    retestSkips = readSkips(skips)

    # Find testcases to retest
    for jobTypeDir in (os.path.join(retestRoot, x) for x in os.listdir(retestRoot) if x.startswith("dom" + "-")):
        if "mac" not in jobTypeDir:
            continue  # XXX just for now
        for j in os.listdir(jobTypeDir):
            if "-asan" in buildDir and "-asan" not in jobTypeDir:
                pass   # what's going on here???
            elif j.split("_")[0] in retestSkips:
                print "Skipping " + j + " for " + j.split("_")[0]
            elif "_0_lines" in j:
                print "Skipping a 0-line testcase"
            elif "_reduced" in j:
                job = os.path.join(jobTypeDir, j)
                testcase_leafs = filter(lambda s: s.find("reduced") != -1, os.listdir(job))
                if len(testcase_leafs) == 1:
                    testcase = os.path.join(job, testcase_leafs[0])
                    mtime = os.stat(testcase).st_mtime
                    testcases.append({'testcase': testcase, 'mtime': mtime})

    # Sort so the newest testcases are first
    print "Retesting " + str(len(testcases)) + " testcases..."
    testcases.sort(key=lambda t: t['mtime'], reverse=True)

    i = 0
    bc = domInteresting.BrowserConfig(["--background", buildDir], domInteresting.createCollector.createCollector("DOMFuzz"))
    tempDir = tempfile.mkdtemp("retesting")

    # Retest all the things!
    for t in testcases:
        testcase = t['testcase']
        print testcase
        i += 1
        logPrefix = os.path.join(tempDir, str(i))
        extraPrefs = randomPrefs.grabExtraPrefs(testcase)
        testcaseURL = loopdomfuzz.asFileURL(testcase)
        domresult = domInteresting.BrowserResult(bc, testcaseURL, logPrefix, extraPrefs=extraPrefs, quiet=True)

        #if level > domInteresting.DOM_FINE:
        #    print "Reproduced: " + testcase
        #    with open(logPrefix + "-summary.txt") as f:
        #        for line in f:
        #            print line,

        # Would it be easier to do it this way?

        #with open(os.devnull, "w") as devnull:
        #    p = subprocess.Popen([loopdomfuzz.domInterestingpy, "mozilla-central/obj-firefox-asan-debug/", testcase], stdout=devnull, stderr=subprocess.STDOUT)
        #    if p.wait() > 0:
        #        print "Still reproduces: " + testcase

        # Ideally we'd use something like "lithium-command.txt" to get the right --valgrind args, etc...
        # (but we don't want the --min-level option)

        # Or this way?

        #lithArgs = ["--strategy=check-only", loopdomfuzz.domInterestingpy, buildInfo.buildDir, testcase]
        #
        #(lithResult, lithDetails) = lithOps.runLithium(lithArgs, logPrefix, options.targetTime)
        #if lithResult == lithOps.LITH_RETESTED_STILL_INTERESTING:
        #   print "Reproduced: " + testcase

    shutil.rmtree(tempDir)


if __name__ == "__main__":
    retestAll()

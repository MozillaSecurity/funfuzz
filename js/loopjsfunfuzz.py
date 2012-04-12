#!/usr/bin/env python

import os
import random
import shutil
import subprocess
import sys

from optparse import OptionParser

p0 = os.path.dirname(os.path.abspath(__file__))
interestingpy = os.path.join(p0, 'jsInteresting.py')

import jsInteresting
import pinpoint
import compareJIT

parser = OptionParser()
parser.disable_interspersed_args()
parser.add_option("--comparejit",
                  action = "store_true", dest = "useCompareJIT",
                  default = False,
                  help = "After running the fuzzer, run the FCM lines against the engine in two configurations and compare the output.")
parser.add_option("--random-flags",
                  action = "store_true", dest = "randomFlags",
                  default = False,
                  help = "Pass a random set of flags (-m, -j, etc) to the js engine")
parser.add_option("--fuzzjs",
                  action = "store", dest = "fuzzjs",
                  default = os.path.join(p0, "jsfunfuzz.js"),
                  help = "Which fuzzer to run (e.g. jsfunfuzz.js or regexpfuzz.js)")
parser.add_option("--repo",
                  action = "store", dest = "repo",
                  default = os.path.expanduser("~/trees/mozilla-central/"),
                  help = "The hg repository (e.g. ~/trees/mozilla-central/), for bisection")
parser.add_option("--valgrind",
                  action = "store_true", dest = "valgrind",
                  default = False,
                  help = "use valgrind with a reasonable set of options")
options, args = parser.parse_args(sys.argv[1:])

if options.valgrind and options.useCompareJIT:
    print "Note: When running comparejit, the --valgrind option will be ignored"

timeout = int(args[0])
knownPath = os.path.expanduser(args[1])
engine = args[2]
engineFlags = args[3:]
# This is the original jsfunfuzz file from the jsfunfuzz directory, with full paths.
jsfunfuzzToBeUsed = options.fuzzjs
# This is the local jsfunfuzz file to be used.
#jsfunfuzzToBeUsed = 'jsfunfuzz.js'
runThis = [engine] + engineFlags + ["-e", "maxRunTime=" + str(timeout*(1000/2)), "-f", jsfunfuzzToBeUsed]

def showtail(filename):
    cmd = []
    cmd.append('tail')
    cmd.append('-n')
    cmd.append('20')
    cmd.append(filename)
    print ' '.join(cmd)
    print ""
    subprocess.call(cmd)
    print ""
    print ""


def many_timed_runs():
    global engineFlags
    iteration = 0

    jsunhappyArgsWithoutRunThis = ["--timeout=" + str(timeout)]
    if options.valgrind:
        jsunhappyArgsWithoutRunThis.append("--valgrind")
    jsunhappyArgsWithoutRunThis.append(knownPath)

    #shutil.copy2(options.fuzzjs, 'backupJsfunfuzz.js')
    while True:

        if options.randomFlags:
            # Grab a flag set from flagCombos
            engineFlags = random.choice(jsInteresting.flagCombos)
            if random.randint(0, 5) == 0:
                # Test a subset of the flags, in random order
                engineFlags = random.sample(engineFlags, random.randint(0, len(engineFlags)))

        runThis = [engine] + engineFlags + ["-e", "maxRunTime=" + str(timeout*(1000/2)), "-f", jsfunfuzzToBeUsed]
        jsunhappyArgs = jsunhappyArgsWithoutRunThis + runThis
        jsunhappyOptions = jsInteresting.parseOptions(jsunhappyArgs)

        iteration += 1

        if False:
            # Integration of jandem's method fuzzer with jsfunfuzz
            # Keep regenerating new objects together with jsfunfuzz.js
            shutil.copy2('backupJsfunfuzz.js', 'jsfunfuzz.js')
            # Run 4test.py and output to current directory.
            subprocess.call(['python', '-u', tempDir + os.sep + '..' + os.sep + '4test.py', engine, '.'])

            # Splice jsfunfuzz.js with current.js from 4test.py
            [before2, after2] = fuzzSpliceHacky(open('jsfunfuzz.js'))
            newfileLines2 = before2 + linesWith(open('current.js'), "") + after2
            writeLinesToFile(newfileLines2, 'jsfunfuzz.js')

        logPrefix = tempDir + os.sep + "w" + str(iteration)

        level = jsInteresting.jsfunfuzzLevel(jsunhappyOptions, logPrefix)

        oklevel = jsInteresting.JS_KNOWN_CRASH
        if jsfunfuzzToBeUsed.find("jsfunfuzz") != -1:
            # Allow hangs. Allow abnormal exits in js shell (OOM) and xpcshell (bug 613142).
            # Switch to allowing jsfunfuzz not finishing and deciding to exit, after Fx 4 and integration of jandem's method fuzzer
            # FIXME: jandem's method fuzzer cannot work with JS_DECIDED_TO_EXIT, currently if the latter is allowed, only pure jsfunfuzz.js should be used.
            # The method fuzzer needs another run of objectTester.js from bug 630996, because it doesn't have evalcx.
            # The method fuzzer also needs its wrap() function removed.
            # When running xpcshell, ./run-mozilla-sh appears not necessary, but remember to append LD_LIBRARY_PATH=. especially on Linux.
            # I also had to remove --random-flags and any CLI flags, because -a isn't supported like it is in the js shell, as an example.
            # All in all, xpcshell support is still largely blocked because of bug 613142.
            oklevel = jsInteresting.JS_ABNORMAL_EXIT if os.path.join('build', 'dist', 'js') not in engine else jsInteresting.JS_VG_AMISS
        elif jsfunfuzzToBeUsed.find("regexpfuzz") != -1:
            # Allow hangs (bug ??????)
            oklevel = jsInteresting.JS_TIMED_OUT

        if level > oklevel:
            showtail(logPrefix + "-out")
            showtail(logPrefix + "-err")

            # splice jsfunfuzz.js with `grep FRC wN-out`
            filenameToReduce = logPrefix + "-reduced.js"
            [before, after] = fuzzSplice(open(jsfunfuzzToBeUsed))
            newfileLines = before + linesWith(open(logPrefix + "-out"), "FRC") + after
            writeLinesToFile(newfileLines, logPrefix + "-orig.js")
            writeLinesToFile(newfileLines, filenameToReduce)

            # Run Lithium and autobisect (make a reduced testcase and find a regression window)
            itest = [interestingpy]
            if options.valgrind:
                itest.append("--valgrind")
            itest.append("--minlevel=" + str(level))
            itest.append("--timeout=" + str(timeout))
            itest.append(knownPath)
            alsoRunChar = (level > jsInteresting.JS_DECIDED_TO_EXIT)
            alsoReduceEntireFile = (level > jsInteresting.JS_OVERALL_MISMATCH)
            pinpoint.pinpoint(itest, logPrefix, engine, engineFlags, filenameToReduce, options.repo, alsoRunChar=alsoRunChar, alsoReduceEntireFile=alsoReduceEntireFile)

        else:
            if options.useCompareJIT and level == jsInteresting.JS_FINE and os.path.join('build', 'dist', 'js') not in engine:
                jitcomparelines = linesWith(open(logPrefix + "-out"), "FCM") + ["try{print(uneval(this));}catch(e){}"]
                jitcomparefilename = logPrefix + "-cj-in.js"
                writeLinesToFile(jitcomparelines, jitcomparefilename)
                compareJIT.compareJIT(engine, jitcomparefilename, logPrefix + "-cj", knownPath, options.repo, timeout, deleteBoring=True)
            os.remove(logPrefix + "-out")
            os.remove(logPrefix + "-err")
            if (os.path.exists(logPrefix + "-crash")):
                os.remove(logPrefix + "-crash")
            if (os.path.exists(logPrefix + "-vg.xml")):
                os.remove(logPrefix + "-vg.xml")
            if (os.path.exists(logPrefix + "-core.gz")):
                os.remove(logPrefix + "-core.gz")
            if (os.path.exists(logPrefix + "-cj-initial-r5-core.gz")):
                os.remove(logPrefix + "-cj-initial-r5-core.gz")


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

def fuzzSpliceHacky(file):
    '''Returns the lines of a file, minus the ones between the two lines specified below'''
    before = []
    after = []
    for line in file:
        before.append(line)
        if line.find("// 1. grep tryIt LOGFILE") != -1:
            break
    for line in file:
        if line.find("// 2. Paste the result between ") != -1:
            after.append(line)
            break
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


createTempDir()
try:
    many_timed_runs()
except KeyboardInterrupt:
    # If the user presses Ctrl-C to stop multi_timed_run, overwrite jsfunfuzz.js with the original.
    #shutil.copy2('backupJsfunfuzz.js', 'jsfunfuzz.js')
    pass

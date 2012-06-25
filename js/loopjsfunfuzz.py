#!/usr/bin/env python

from __future__ import with_statement

import os
import random
import shutil
import subprocess
import sys
import time
from optparse import OptionParser

import compareJIT
import jsInteresting
import pinpoint
import shellFlags

p0 = os.path.dirname(os.path.abspath(__file__))
interestingpy = os.path.abspath(os.path.join(p0, 'jsInteresting.py'))
p1 = os.path.abspath(os.path.join(p0, os.pardir, 'util'))
sys.path.append(p1)
from subprocesses import createWtmpDir
from fileManipulation import fuzzSplice, linesWith, writeLinesToFile
import lithOps

def parseOpts(args):
    parser = OptionParser()
    parser.disable_interspersed_args()
    parser.add_option("--comparejit",
                      action = "store_true", dest = "useCompareJIT",
                      default = False,
                      help = "After running the fuzzer, run the FCM lines against the engine " + \
                             "in two configurations and compare the output.")
    parser.add_option("--random-flags",
                      action = "store_true", dest = "randomFlags",
                      default = False,
                      help = "Pass a random set of flags (-m, -j, etc) to the js engine")
    parser.add_option("--fuzzjs",
                      action = "store", dest = "fuzzjs",
                      default = os.path.join(p0, "jsfunfuzz.js"),
                      help = "Which fuzzer to run (e.g. jsfunfuzz.js)")
    parser.add_option("--repo",
                      action = "store", dest = "repo",
                      default = os.path.expanduser("~/trees/mozilla-central/"),
                      help = "The hg repository (e.g. ~/trees/mozilla-central/), for bisection")
    parser.add_option("--valgrind",
                      action = "store_true", dest = "valgrind",
                      default = False,
                      help = "use valgrind with a reasonable set of options")
    options, args = parser.parse_args(args)

    if options.valgrind and options.useCompareJIT:
        print "Note: When running comparejit, the --valgrind option will be ignored"

    options.timeout = int(args[0])
    options.knownPath = os.path.expanduser(args[1])
    options.jsEngine = args[2]
    options.engineFlags = args[3:]

    return options

def showtail(filename):
    # FIXME: Get jsfunfuzz to output start & end of interesting result boundaries instead of this.
    cmd = []
    cmd.extend(['tail', '-n', '20'])
    cmd.append(filename)
    print ' '.join(cmd)
    print
    subprocess.check_call(cmd)
    print
    print

def many_timed_runs(targetTime, args):
    options = parseOpts(args)
    engineFlags = options.engineFlags  # engineFlags is overwritten later if --random-flags is set.
    wtmpDir = createWtmpDir(os.getcwdu())
    startTime = time.time()

    iteration = 0
    while True:
        if targetTime and time.time() > startTime + targetTime:
            print "Out of time!"
            if len(os.listdir(wtmpDirNum)) == 0:
                os.rmdir(wtmpDirNum)
            return (lithOps.HAPPY, None)

        # Construct command needed to loop jsfunfuzz fuzzing.
        jsInterestingArgs = []
        jsInterestingArgs.append('--timeout=' + str(options.timeout))
        if options.valgrind:
            jsInterestingArgs.append('--valgrind')
        jsInterestingArgs.append(options.knownPath)
        jsInterestingArgs.append(options.jsEngine)
        if options.randomFlags:
            engineFlags = shellFlags.randomFlagSet(options.jsEngine)
            jsInterestingArgs.extend(engineFlags)
        jsInterestingArgs.extend(['-e', 'maxRunTime=' + str(options.timeout*(1000/2))])
        jsInterestingArgs.extend(['-f', options.fuzzjs])
        jsunhappyOptions = jsInteresting.parseOptions(jsInterestingArgs)

        iteration += 1
        logPrefix = wtmpDir + os.sep + "w" + str(iteration)

        level = jsInteresting.jsfunfuzzLevel(jsunhappyOptions, logPrefix)

        if level != jsInteresting.JS_FINE:
            showtail(logPrefix + "-out.txt")
            showtail(logPrefix + "-err.txt")

            # splice jsfunfuzz.js with `grep FRC wN-out`
            filenameToReduce = logPrefix + "-reduced.js"
            [before, after] = fuzzSplice(options.fuzzjs)
            with open(logPrefix + '-out.txt', 'rb') as f:
                newfileLines = before + linesWith(f.readlines(), "FRC") + after
            writeLinesToFile(newfileLines, logPrefix + "-orig.js")
            writeLinesToFile(newfileLines, filenameToReduce)

            # Run Lithium and autobisect (make a reduced testcase and find a regression window)
            itest = [interestingpy]
            if options.valgrind:
                itest.append("--valgrind")
            itest.append("--minlevel=" + str(level))
            itest.append("--timeout=" + str(options.timeout))
            itest.append(options.knownPath)
            alsoRunChar = (level > jsInteresting.JS_DECIDED_TO_EXIT)
            alsoReduceEntireFile = (level > jsInteresting.JS_OVERALL_MISMATCH)
            (lithResult, lithDetails) = pinpoint.pinpoint(itest, logPrefix, options.jsEngine, engineFlags, filenameToReduce,
                                                          options.repo, targetTime, alsoRunChar=alsoRunChar,
                                                          alsoReduceEntireFile=alsoReduceEntireFile)
            if targetTime:
                return (lithResult, lithDetails)

        else:
            shellIsDeterministic = os.path.join('build', 'dist', 'js') not in options.jsEngine # bug 751700
            flagsAreDeterministic = "--dump-bytecode" not in engineFlags
            if options.useCompareJIT and level == jsInteresting.JS_FINE and \
                    shellIsDeterministic and flagsAreDeterministic:
                with open(logPrefix + '-out.txt', 'rb') as f:
                    jitcomparelines = linesWith(f.readlines(), "FCM") + \
                        ["try{print(uneval(this));}catch(e){}"]
                jitcomparefilename = logPrefix + "-cj-in.js"
                writeLinesToFile(jitcomparelines, jitcomparefilename)
                (lithResult, lithDetails) = compareJIT.compareJIT(options.jsEngine, engineFlags, jitcomparefilename,
                                                                  logPrefix + "-cj", options.knownPath, options.repo,
                                                                  options.timeout, targetTime, True)
                if targetTime and lithResult != lithOps.HAPPY:
                    return (lithResult, lithDetails)
            jsInteresting.deleteLogs(logPrefix)

if __name__ == "__main__":
    many_timed_runs(None, sys.argv[1:])

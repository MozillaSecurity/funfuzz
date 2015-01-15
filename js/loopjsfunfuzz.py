#!/usr/bin/env python

import json
import os
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
from subprocesses import createWtmpDir, normExpUserPath
from fileManipulation import fuzzSplice, linesStartingWith, writeLinesToFile
from inspectShell import queryBuildConfiguration
import lithOps
import linkJS

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
    parser.add_option("--repo",
                      action = "store", dest = "repo",
                      default = os.path.expanduser("~/trees/mozilla-central/"),
                      help = "The hg repository (e.g. ~/trees/mozilla-central/), for bisection")
    parser.add_option("--build",
                      action = "store", dest = "buildOptionsStr",
                      help = "The build options, for bisection",
                      default = None) # if you run loopjsfunfuzz.py directly without a --build, pinpoint will try to guess
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

def linkFuzzer(target_fn, repo, prologue):
    source_base = p0
    file_list_fn = normExpUserPath(os.path.join(p0, "files-to-link.txt"))
    linkJS.linkJS(target_fn, file_list_fn, source_base, prologue)

def makeRegressionTestPrologue(repo, regressionTestListFile):
    """Generate a JS string to tell jsfunfuzz where to find SpiderMonkey's regression tests"""

    # We use json.dumps to escape strings (Windows paths have backslashes).
    return """
        const regressionTestList = read(%s).match(/.+/g);
        const regressionTestsRoot = %s;
        const libdir = regressionTestsRoot + %s; // needed by jit-tests
    """ % (
        json.dumps(os.path.abspath(normExpUserPath(regressionTestListFile))),
        json.dumps(normExpUserPath(repo) + os.sep),
        json.dumps(os.path.join('js', 'src', 'jit-test', 'lib') + os.sep),
    )

def inTreeRegressionTests(repo):
    jitTests = jsFilesIn(os.path.join(repo, 'js', 'src', 'jit-test', 'tests'))
    jsTests = jsFilesIn(os.path.join(repo, 'js', 'src', 'tests'))
    return jitTests + jsTests

def jsFilesIn(root):
    return [os.path.join(path, filename)
                      for path, dirs, files in os.walk(normExpUserPath(root))
                      for filename in files
                      if filename.endswith('.js')]


def many_timed_runs(targetTime, wtmpDir, args):
    options = parseOpts(args)
    engineFlags = options.engineFlags  # engineFlags is overwritten later if --random-flags is set.
    startTime = time.time()

    if os.path.isdir(normExpUserPath(options.repo)):
        regressionTestListFile = normExpUserPath(os.path.join(wtmpDir, "regression-tests.list"))
        with open(regressionTestListFile, "wb") as f:
            for fn in inTreeRegressionTests(options.repo):
                f.write(fn + "\n")
        regressionTestPrologue = makeRegressionTestPrologue(options.repo, regressionTestListFile)
    else:
        regressionTestPrologue = ""

    fuzzjs = normExpUserPath(os.path.join(wtmpDir, "jsfunfuzz.js"))
    linkFuzzer(fuzzjs, options.repo, regressionTestPrologue)

    iteration = 0
    while True:
        if targetTime and time.time() > startTime + targetTime:
            print "Out of time!"
            os.remove(fuzzjs)
            if len(os.listdir(wtmpDir)) == 0:
                os.rmdir(wtmpDir)
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
        jsInterestingArgs.extend(['-f', fuzzjs])
        jsunhappyOptions = jsInteresting.parseOptions(jsInterestingArgs)

        iteration += 1
        logPrefix = normExpUserPath(os.path.join(wtmpDir, "w" + str(iteration)))

        level = jsInteresting.jsfunfuzzLevel(jsunhappyOptions, logPrefix)

        if level != jsInteresting.JS_FINE:
            showtail(logPrefix + "-out.txt")
            showtail(logPrefix + "-err.txt")

            # splice jsfunfuzz.js with `grep FRC wN-out`
            filenameToReduce = logPrefix + "-reduced.js"
            [before, after] = fuzzSplice(fuzzjs)

            with open(logPrefix + '-out.txt', 'rb') as f:
                newfileLines = before + [l.replace('/*FRC*/', '') for l in linesStartingWith(f, "/*FRC*/")] + after
            writeLinesToFile(newfileLines, logPrefix + "-orig.js")
            writeLinesToFile(newfileLines, filenameToReduce)

            # Run Lithium and autobisect (make a reduced testcase and find a regression window)
            itest = [interestingpy]
            if options.valgrind:
                itest.append("--valgrind")
            itest.append("--minlevel=" + str(level))
            itest.append("--timeout=" + str(options.timeout))
            itest.append(options.knownPath)
            (lithResult, lithDetails) = pinpoint.pinpoint(itest, logPrefix, options.jsEngine, engineFlags, filenameToReduce,
                                                          options.repo, options.buildOptionsStr, targetTime, level)
            if targetTime:
                return (lithResult, lithDetails)

        else:
            shellIsDeterministic = queryBuildConfiguration(options.jsEngine, 'more-deterministic')
            flagsAreDeterministic = "--dump-bytecode" not in engineFlags and '-D' not in engineFlags
            if options.useCompareJIT and level == jsInteresting.JS_FINE and \
                    shellIsDeterministic and flagsAreDeterministic:
                with open(logPrefix + '-out.txt', 'rb') as f:
                    jitcomparelines = (
                        ["dumpObject = function() { };\n",
                         "dumpHeapComplete = function() { };\n",
                         "// DDBEGIN\n"] +
                        [l.replace('/*FCM*/', '') for l in linesStartingWith(f, "/*FCM*/")] +
                        ["\ntry{print(uneval(this));}catch(e){}\n", "// DDEND\n"]
                    )
                jitcomparefilename = logPrefix + "-cj-in.js"
                writeLinesToFile(jitcomparelines, jitcomparefilename)
                (lithResult, lithDetails) = compareJIT.compareJIT(options.jsEngine, engineFlags, jitcomparefilename,
                                                                  logPrefix + "-cj", options.knownPath, options.repo,
                                                                  options.buildOptionsStr, options.timeout, targetTime)
                if lithResult == lithOps.HAPPY:
                    os.remove(jitcomparefilename)
                if targetTime and lithResult != lithOps.HAPPY:
                    jsInteresting.deleteLogs(logPrefix)
                    return (lithResult, lithDetails)
            jsInteresting.deleteLogs(logPrefix)

if __name__ == "__main__":
    many_timed_runs(None, createWtmpDir(os.getcwdu()), sys.argv[1:])

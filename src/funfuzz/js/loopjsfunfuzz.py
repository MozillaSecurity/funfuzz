#!/usr/bin/env python
# coding=utf-8
# pylint: disable=fixme,invalid-name,missing-docstring,no-member,too-many-branches
# pylint: disable=too-many-locals,too-many-statements
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import absolute_import, print_function

import json
import os
import subprocess
import sys
import time
from optparse import OptionParser  # pylint: disable=deprecated-module

from . import compareJIT
from . import jsInteresting
from . import pinpoint
from . import shellFlags
from ..util import createCollector
from ..util import fileManipulation
from ..util import lithOps
from ..util import linkJS
from ..util import subprocesses as sps

p0 = os.path.dirname(os.path.abspath(__file__))
interestingpy = os.path.abspath(os.path.join(p0, 'jsInteresting.py'))


def parseOpts(args):
    parser = OptionParser()
    parser.disable_interspersed_args()
    parser.add_option("--comparejit",
                      action="store_true", dest="useCompareJIT",
                      default=False,
                      help="After running the fuzzer, run the FCM lines against the engine "
                           "in two configurations and compare the output.")
    parser.add_option("--random-flags",
                      action="store_true", dest="randomFlags",
                      default=False,
                      help="Pass a random set of flags (e.g. --ion-eager) to the js engine")
    parser.add_option("--repo",
                      action="store", dest="repo",
                      default=os.path.expanduser("~/trees/mozilla-central/"),
                      help="The hg repository (e.g. ~/trees/mozilla-central/), for bisection")
    parser.add_option("--build",
                      action="store", dest="buildOptionsStr",
                      help="The build options, for bisection",
                      default=None)  # if you run loopjsfunfuzz.py directly without --build, pinpoint will try to guess
    parser.add_option("--valgrind",
                      action="store_true", dest="valgrind",
                      default=False,
                      help="use valgrind with a reasonable set of options")
    options, args = parser.parse_args(args)

    if options.valgrind and options.useCompareJIT:
        print("Note: When running comparejit, the --valgrind option will be ignored")

    # kill js shell if it runs this long.
    # jsfunfuzz will quit after half this time if it's not ilooping.
    # higher = more complex mixing, especially with regression tests.
    # lower = less time wasted in timeouts and in compareJIT testcases that are thrown away due to OOMs.
    options.timeout = int(args[0])

    # FIXME: We can probably remove args[1]
    options.knownPath = 'mozilla-central'
    options.jsEngine = args[2]
    options.engineFlags = args[3:]

    return options


def showtail(filename):
    # FIXME: Get jsfunfuzz to output start & end of interesting result boundaries instead of this.
    cmd = []
    cmd.extend(['tail', '-n', '20'])
    cmd.append(filename)
    print(" ".join(cmd))
    print()
    subprocess.check_call(cmd)
    print()
    print()


def linkFuzzer(target_fn, prologue):
    source_base = p0
    file_list_fn = sps.normExpUserPath(os.path.join(p0, "files-to-link.txt"))
    linkJS.linkJS(target_fn, file_list_fn, source_base, prologue)


def makeRegressionTestPrologue(repo):
    """Generate a JS string to tell jsfunfuzz where to find SpiderMonkey's regression tests."""
    repo = sps.normExpUserPath(repo) + os.sep

    return """
const regressionTestsRoot = %s;
const libdir = regressionTestsRoot + %s; // needed by jit-tests
const regressionTestList = %s;
""" % (json.dumps(repo),
       json.dumps(os.path.join('js', 'src', 'jit-test', 'lib') + os.sep),
       json.dumps(inTreeRegressionTests(repo)))


def inTreeRegressionTests(repo):
    jitTests = jsFilesIn(len(repo), os.path.join(repo, 'js', 'src', 'jit-test', 'tests'))
    jsTests = jsFilesIn(len(repo), os.path.join(repo, 'js', 'src', 'tests'))
    return jitTests + jsTests


def jsFilesIn(repoPathLength, root):
    return [os.path.join(path, filename)[repoPathLength:]
            for path, _dirs, files in os.walk(sps.normExpUserPath(root))
            for filename in files
            if filename.endswith('.js')]


def many_timed_runs(targetTime, wtmpDir, args, collector):
    options = parseOpts(args)
    engineFlags = options.engineFlags  # engineFlags is overwritten later if --random-flags is set.
    startTime = time.time()

    if os.path.isdir(sps.normExpUserPath(options.repo)):
        regressionTestPrologue = makeRegressionTestPrologue(options.repo)
    else:
        regressionTestPrologue = ""

    fuzzjs = sps.normExpUserPath(os.path.join(wtmpDir, "jsfunfuzz.js"))
    linkFuzzer(fuzzjs, regressionTestPrologue)

    iteration = 0
    while True:
        if targetTime and time.time() > startTime + targetTime:
            print("Out of time!")
            os.remove(fuzzjs)
            if not os.listdir(wtmpDir):
                os.rmdir(wtmpDir)
            break

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
        jsInterestingArgs.extend(['-e', 'maxRunTime=' + str(options.timeout * (1000 / 2))])
        jsInterestingArgs.extend(['-f', fuzzjs])
        jsInterestingOptions = jsInteresting.parseOptions(jsInterestingArgs)

        iteration += 1
        logPrefix = sps.normExpUserPath(os.path.join(wtmpDir, "w" + str(iteration)))

        res = jsInteresting.ShellResult(jsInterestingOptions, jsInterestingOptions.jsengineWithArgs, logPrefix, False)

        if res.lev != jsInteresting.JS_FINE:
            showtail(logPrefix + "-out.txt")
            showtail(logPrefix + "-err.txt")

            # splice jsfunfuzz.js with `grep "/*FRC-" wN-out`
            filenameToReduce = logPrefix + "-reduced.js"
            [before, after] = fileManipulation.fuzzSplice(fuzzjs)

            with open(logPrefix + '-out.txt', 'rb') as f:
                newfileLines = before + [
                    l.replace('/*FRC-', '/*') for l in fileManipulation.linesStartingWith(f, "/*FRC-")] + after
            fileManipulation.writeLinesToFile(newfileLines, logPrefix + "-orig.js")
            fileManipulation.writeLinesToFile(newfileLines, filenameToReduce)

            # Run Lithium and autobisect (make a reduced testcase and find a regression window)
            itest = [interestingpy]
            if options.valgrind:
                itest.append("--valgrind")
            itest.append("--minlevel=" + str(res.lev))
            itest.append("--timeout=" + str(options.timeout))
            itest.append(options.knownPath)
            (lithResult, _lithDetails, autoBisectLog) = pinpoint.pinpoint(
                itest, logPrefix, options.jsEngine, engineFlags, filenameToReduce, options.repo,
                options.buildOptionsStr, targetTime, res.lev)

            # Upload with final output
            if lithResult == lithOps.LITH_FINISHED:
                fargs = jsInterestingOptions.jsengineWithArgs[:-1] + [filenameToReduce]
                retestResult = jsInteresting.ShellResult(jsInterestingOptions, fargs, logPrefix + "-final", False)
                if retestResult.lev > jsInteresting.JS_FINE:
                    res = retestResult
                    quality = 0
                else:
                    quality = 6
            else:
                quality = 10

            # ddsize = lithOps.ddsize(filenameToReduce)
            print("Submitting %s (quality=%s) at %s" % (filenameToReduce, quality, time.asctime()))

            metadata = {}
            if autoBisectLog:
                metadata = {"autoBisectLog": ''.join(autoBisectLog)}
            collector.submit(res.crashInfo, filenameToReduce, quality, metaData=metadata)
            print("Submitted %s" % filenameToReduce)

        else:
            flagsAreDeterministic = "--dump-bytecode" not in engineFlags and '-D' not in engineFlags
            if options.useCompareJIT and res.lev == jsInteresting.JS_FINE and \
                    jsInterestingOptions.shellIsDeterministic and flagsAreDeterministic:
                linesToCompare = jitCompareLines(logPrefix + '-out.txt', "/*FCM*/")
                jitcomparefilename = logPrefix + "-cj-in.js"
                fileManipulation.writeLinesToFile(linesToCompare, jitcomparefilename)
                anyBug = compareJIT.compareJIT(options.jsEngine, engineFlags, jitcomparefilename,
                                               logPrefix + "-cj", options.repo,
                                               options.buildOptionsStr, targetTime, jsInterestingOptions)
                if not anyBug:
                    os.remove(jitcomparefilename)

            jsInteresting.deleteLogs(logPrefix)


def jitCompareLines(jsfunfuzzOutputFilename, marker):
    """Create a compareJIT file, using the lines marked by jsfunfuzz as valid for comparison."""
    lines = [
        "backtrace = function() { };\n",
        "dumpHeap = function() { };\n",
        "dumpObject = function() { };\n",
        "dumpStringRepresentation = function() { };\n",
        "evalInWorker = function() { };\n",
        "getBacktrace = function() { };\n",
        "getLcovInfo = function() { };\n",
        "isAsmJSCompilationAvailable = function() { };\n",
        "offThreadCompileScript = function() { };\n",
        "printProfilerEvents = function() { };\n",
        "saveStack = function() { };\n",
        "wasmIsSupported = function() { return true; };\n",
        "// DDBEGIN\n"
    ]
    with open(jsfunfuzzOutputFilename, 'rb') as f:
        for line in f:
            if line.startswith(marker):
                sline = line[len(marker):]
                divisionIsInconsistent = sps.isWin  # Really 'if MSVC' -- revisit if we add clang builds on Windows
                if divisionIsInconsistent and mightUseDivision(sline):
                    pass
                elif "newGlobal" in sline and "wasmIsSupported" in sline:
                    # We only override wasmIsSupported above for the main global.
                    # Hopefully, any imported tests that try to use wasmIsSupported within a newGlobal
                    # will do so in a straightforward way where everything is on one line.
                    pass
                else:
                    lines.append(sline)
    lines += [
        "\ntry{print(uneval(this));}catch(e){}\n",
        "// DDEND\n"
    ]
    return lines


def mightUseDivision(code):
    # Work around MSVC division inconsistencies (bug 948321)
    # by leaving division out of *-cj-in.js files on Windows.
    # (Unfortunately, this will also match regexps and a bunch
    # of other things.)
    i = 0
    while i < len(code):
        if code[i] == '/':
            if i + 1 < len(code) and (code[i + 1] == '/' or code[i + 1] == '*'):
                # An open-comment like "//" or "/*" is okay. Skip the next character.
                i += 1
            elif i and code[i - 1] == '*':
                # A close-comment like "*/" is okay too.
                pass
            else:
                # Plain "/" could be division (or regexp or something else)
                return True
        i += 1
    return False


assert not mightUseDivision("//")
assert not mightUseDivision("// a")
assert not mightUseDivision("/*FOO*/")
assert mightUseDivision("a / b")
assert mightUseDivision("eval('/**/'); a / b;")
assert mightUseDivision("eval('//x'); a / b;")


if __name__ == "__main__":
    many_timed_runs(None, sps.createWtmpDir(os.getcwdu()), sys.argv[1:], createCollector.createCollector("jsfunfuzz"))

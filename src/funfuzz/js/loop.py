# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Allows the funfuzz harness to run continuously.
"""

from __future__ import absolute_import, print_function  # isort:skip

import json
from optparse import OptionParser  # pylint: disable=deprecated-module
import os
import subprocess
import sys
import time

from . import compare_jit
from . import js_interesting
from . import shell_flags
from ..util import create_collector
from ..util import file_manipulation
from ..util import link_js
from ..util import lithium_helpers
from ..util import subprocesses as sps


def parseOpts(args):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    parser = OptionParser()
    parser.disable_interspersed_args()
    parser.add_option("--compare-jit",
                      action="store_true", dest="use_compare_jit",
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
                      action="store", dest="build_options_str",
                      help="The build options, for bisection",
                      default=None)  # if you run loop directly w/o --build, lithium_helpers.pinpoint will try to guess
    parser.add_option("--valgrind",
                      action="store_true", dest="valgrind",
                      default=False,
                      help="use valgrind with a reasonable set of options")
    options, args = parser.parse_args(args)

    if options.valgrind and options.use_compare_jit:
        print("Note: When running compare_jit, the --valgrind option will be ignored")

    # kill js shell if it runs this long.
    # jsfunfuzz will quit after half this time if it's not ilooping.
    # higher = more complex mixing, especially with regression tests.
    # lower = less time wasted in timeouts and in compare_jit testcases that are thrown away due to OOMs.
    options.timeout = int(args[0])
    options.jsEngine = args[1]
    options.engineFlags = args[2:]

    return options


def showtail(filename):  # pylint: disable=missing-docstring
    # pylint: disable=fixme
    # FIXME: Get jsfunfuzz to output start & end of interesting result boundaries instead of this.
    cmd = []
    cmd.extend(["tail", "-n", "20"])
    cmd.append(filename)
    print(" ".join(cmd))
    print()
    subprocess.check_call(cmd)
    print()
    print()


def linkFuzzer(target_fn, prologue):  # pylint: disable=invalid-name,missing-docstring
    source_base = os.path.dirname(os.path.abspath(__file__))
    file_list_fn = sps.normExpUserPath(os.path.join(source_base, "files_to_link.txt"))
    link_js.link_js(target_fn, file_list_fn, source_base, prologue)


def makeRegressionTestPrologue(repo):  # pylint: disable=invalid-name,missing-docstring,missing-param-doc
    # pylint: disable=missing-return-doc,missing-return-type-doc,missing-type-doc
    """Generate a JS string to tell jsfunfuzz where to find SpiderMonkey's regression tests."""
    repo = sps.normExpUserPath(repo) + os.sep

    return """
const regressionTestsRoot = %s;
const libdir = regressionTestsRoot + %s; // needed by jit-tests
const regressionTestList = %s;
""" % (json.dumps(repo),
       json.dumps(os.path.join("js", "src", "jit-test", "lib") + os.sep),
       json.dumps(inTreeRegressionTests(repo)))


def inTreeRegressionTests(repo):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    jit_tests = jsFilesIn(len(repo), os.path.join(repo, "js", "src", "jit-test", "tests"))
    js_tests = jsFilesIn(len(repo), os.path.join(repo, "js", "src", "tests"))
    return jit_tests + js_tests


def jsFilesIn(repoPathLength, root):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    return [os.path.join(path, filename)[repoPathLength:]
            for path, _dirs, files in os.walk(sps.normExpUserPath(root))
            for filename in files
            if filename.endswith(".js")]


def many_timed_runs(targetTime, wtmpDir, args, collector):  # pylint: disable=invalid-name,missing-docstring,too-complex
    # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    options = parseOpts(args)
    # engineFlags is overwritten later if --random-flags is set.
    engineFlags = options.engineFlags  # pylint: disable=invalid-name
    startTime = time.time()  # pylint: disable=invalid-name

    if os.path.isdir(sps.normExpUserPath(options.repo)):
        regressionTestPrologue = makeRegressionTestPrologue(options.repo)  # pylint: disable=invalid-name
    else:
        regressionTestPrologue = ""  # pylint: disable=invalid-name

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
        js_interesting_args = []
        js_interesting_args.append("--timeout=" + str(options.timeout))
        if options.valgrind:
            js_interesting_args.append("--valgrind")
        js_interesting_args.append(options.jsEngine)
        if options.randomFlags:
            engineFlags = shell_flags.random_flag_set(options.jsEngine)  # pylint: disable=invalid-name
            js_interesting_args.extend(engineFlags)
        js_interesting_args.extend(["-e", "maxRunTime=" + str(options.timeout * (1000 // 2))])
        js_interesting_args.extend(["-f", fuzzjs])
        js_interesting_options = js_interesting.parseOptions(js_interesting_args)

        iteration += 1
        logPrefix = sps.normExpUserPath(os.path.join(wtmpDir, "w" + str(iteration)))  # pylint: disable=invalid-name

        res = js_interesting.ShellResult(js_interesting_options,
                                         # pylint: disable=no-member
                                         js_interesting_options.jsengineWithArgs, logPrefix, False)

        if res.lev != js_interesting.JS_FINE:
            showtail(logPrefix + "-out.txt")
            showtail(logPrefix + "-err.txt")

            # splice jsfunfuzz.js with `grep "/*FRC-" wN-out`
            filenameToReduce = logPrefix + "-reduced.js"  # pylint: disable=invalid-name
            [before, after] = file_manipulation.fuzzSplice(fuzzjs)

            with open(logPrefix + "-out.txt", "r") as f:
                newfileLines = before + [  # pylint: disable=invalid-name
                    l.replace("/*FRC-", "/*") for l in file_manipulation.linesStartingWith(f, "/*FRC-")] + after
            with open(logPrefix + "-orig.js", "w") as f:
                f.writelines(newfileLines)
            with open(filenameToReduce, "w") as f:
                f.writelines(newfileLines)

            # Run Lithium and autobisectjs (make a reduced testcase and find a regression window)
            interestingpy = "funfuzz.js.js_interesting"  # pylint: disable=invalid-name
            itest = [interestingpy]
            if options.valgrind:
                itest.append("--valgrind")
            itest.append("--minlevel=" + str(res.lev))
            itest.append("--timeout=" + str(options.timeout))
            (lithResult, _lithDetails, autoBisectLog) = lithium_helpers.pinpoint(  # pylint: disable=invalid-name
                itest, logPrefix, options.jsEngine, engineFlags, filenameToReduce, options.repo,
                options.build_options_str, targetTime, res.lev)

            # Upload with final output
            if lithResult == lithium_helpers.LITH_FINISHED:
                # pylint: disable=no-member
                fargs = js_interesting_options.jsengineWithArgs[:-1] + [filenameToReduce]
                # pylint: disable=invalid-name
                retestResult = js_interesting.ShellResult(js_interesting_options, fargs, logPrefix + "-final", False)
                if retestResult.lev > js_interesting.JS_FINE:
                    res = retestResult
                    quality = 0
                else:
                    quality = 6
            else:
                quality = 10

            print("Submitting %s (quality=%s) at %s" % (filenameToReduce, quality, time.asctime()))

            metadata = {}
            if autoBisectLog:
                metadata = {"autoBisectLog": "".join(autoBisectLog)}
            collector.submit(res.crashInfo, filenameToReduce, quality, metaData=metadata)
            print("Submitted %s" % filenameToReduce)

        else:
            are_flags_deterministic = "--dump-bytecode" not in engineFlags and "-D" not in engineFlags
            # pylint: disable=no-member
            if options.use_compare_jit and res.lev == js_interesting.JS_FINE and \
                    js_interesting_options.shellIsDeterministic and are_flags_deterministic:
                linesToCompare = jitCompareLines(logPrefix + "-out.txt", "/*FCM*/")  # pylint: disable=invalid-name
                jitcomparefilename = logPrefix + "-cj-in.js"
                with open(jitcomparefilename, "w") as f:
                    f.writelines(linesToCompare)
                # pylint: disable=invalid-name
                anyBug = compare_jit.compare_jit(options.jsEngine, engineFlags, jitcomparefilename,
                                                 logPrefix + "-cj", options.repo,
                                                 options.build_options_str, targetTime, js_interesting_options)
                if not anyBug:
                    os.remove(jitcomparefilename)

            js_interesting.deleteLogs(logPrefix)


def jitCompareLines(jsfunfuzzOutputFilename, marker):  # pylint: disable=invalid-name,missing-param-doc
    # pylint: disable=missing-return-doc,missing-return-type-doc,missing-type-doc
    """Create a compare_jit file, using the lines marked by jsfunfuzz as valid for comparison."""
    lines = [
        "backtrace = function() { };\n",
        "dumpHeap = function() { };\n",
        "dumpObject = function() { };\n",
        "dumpStringRepresentation = function() { };\n",
        "evalInCooperativeThread = function() { };\n",
        "evalInWorker = function() { };\n",
        "getBacktrace = function() { };\n",
        "getLcovInfo = function() { };\n",
        "isAsmJSCompilationAvailable = function() { };\n",
        "offThreadCompileScript = function() { };\n",
        "oomTest = function() { };\n",
        "printProfilerEvents = function() { };\n",
        "saveStack = function() { };\n",
        "wasmIsSupported = function() { return true; };\n",
        "// DDBEGIN\n"
    ]
    with open(jsfunfuzzOutputFilename, "r") as f:
        for line in f:
            if line.startswith(marker):
                sline = line[len(marker):]
                # We only override wasmIsSupported above for the main global.
                # Hopefully, any imported tests that try to use wasmIsSupported within a newGlobal
                # will do so in a straightforward way where everything is on one line.
                if not ("newGlobal" in sline and "wasmIsSupported" in sline):
                    lines.append(sline)
    lines += [
        "\ntry{print(uneval(this));}catch(e){}\n",
        "// DDEND\n"
    ]
    return lines


if __name__ == "__main__":
    # pylint: disable=no-member
    many_timed_runs(None, sps.createWtmpDir(os.getcwdu() if sys.version_info.major == 2 else os.getcwd()),
                    sys.argv[1:], create_collector.createCollector("jsfunfuzz"))

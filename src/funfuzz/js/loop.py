# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Allows the funfuzz harness to run continuously.
"""

from __future__ import absolute_import, print_function, unicode_literals  # isort:skip

import io
import json
from optparse import OptionParser  # pylint: disable=deprecated-module
import os
import sys
import time

from . import compare_jit
from . import js_interesting
from . import link_fuzzer
from . import shell_flags
from ..util import create_collector
from ..util import file_manipulation
from ..util import lithium_helpers
from ..util import os_ops

if sys.version_info.major == 2:
    if os.name == "posix":
        import subprocess32 as subprocess  # pylint: disable=import-error
    from pathlib2 import Path  # pylint: disable=import-error
else:
    from pathlib import Path  # pylint: disable=import-error
    import subprocess


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
                      action="store",
                      dest="repo",
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

    # optparse does not recognize pathlib - we will need to move to argparse
    if options.repo:
        options.repo = Path(options.repo)
    else:
        options.repo = Path.home() / "trees" / "mozilla-central"

    if options.valgrind and options.use_compare_jit:
        print("Note: When running compare_jit, the --valgrind option will be ignored")

    # kill js shell if it runs this long.
    # jsfunfuzz will quit after half this time if it's not ilooping.
    # higher = more complex mixing, especially with regression tests.
    # lower = less time wasted in timeouts and in compare_jit testcases that are thrown away due to OOMs.
    options.timeout = int(args[0])

    # FIXME: We can probably remove args[1]  # pylint: disable=fixme
    options.knownPath = "mozilla-central"
    options.jsEngine = Path(args[2])
    options.engineFlags = args[3:]

    return options


def showtail(filename):  # pylint: disable=missing-docstring
    # pylint: disable=fixme
    # FIXME: Get jsfunfuzz to output start & end of interesting result boundaries instead of this.
    cmd = []
    cmd.extend(["tail", "-n", "20"])
    cmd.append(str(filename))
    print(" ".join(cmd))
    print()
    subprocess.run(cmd, check=True)
    print()
    print()


def makeRegressionTestPrologue(repo):  # pylint: disable=invalid-name,missing-param-doc
    # pylint: disable=missing-return-doc,missing-return-type-doc,missing-type-doc
    """Generate a JS string to tell jsfunfuzz where to find SpiderMonkey's regression tests."""
    return """
const regressionTestsRoot = %s;
const libdir = regressionTestsRoot + %s; // needed by jit-tests
const regressionTestList = %s;
""" % (json.dumps(str(repo) + os.sep),
       json.dumps(os.sep.join(["js", "src", "jit-test", "lib"]) + os.sep),
       json.dumps(inTreeRegressionTests(repo)))


def inTreeRegressionTests(repo):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    jit_tests = jsFilesIn(len(str(repo)), repo / "js" / "src" / "jit-test" / "tests")
    js_tests = jsFilesIn(len(str(repo)), repo / "js" / "src" / "tests")
    return jit_tests + js_tests


def jsFilesIn(repoPathLength, root):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    return [os.path.join(path, filename)[repoPathLength:]
            for path, _dirs, files in os.walk(str(root))
            for filename in files
            if filename.endswith(".js")]


def many_timed_runs(targetTime, wtmpDir, args, collector, ccoverage):  # pylint: disable=invalid-name,missing-docstring
    # pylint: disable=too-many-branches,too-complex,too-many-locals,too-many-statements
    options = parseOpts(args)
    # engineFlags is overwritten later if --random-flags is set.
    engineFlags = options.engineFlags  # pylint: disable=invalid-name
    startTime = time.time()  # pylint: disable=invalid-name

    if options.repo.is_dir():
        regressionTestPrologue = makeRegressionTestPrologue(options.repo)  # pylint: disable=invalid-name
    else:
        regressionTestPrologue = ""  # pylint: disable=invalid-name

    fuzzjs = wtmpDir / "jsfunfuzz.js"

    link_fuzzer.link_fuzzer(fuzzjs, regressionTestPrologue)
    assert fuzzjs.is_file()

    iteration = 0
    while True:
        if targetTime and time.time() > startTime + targetTime:
            print("Out of time!")
            fuzzjs.unlink()
            if not os.listdir(str(wtmpDir)):
                wtmpDir.rmdir()
            break

        # Construct command needed to loop jsfunfuzz fuzzing.
        js_interesting_args = []
        js_interesting_args.append("--timeout=" + str(options.timeout))
        if options.valgrind:
            js_interesting_args.append("--valgrind")
        js_interesting_args.append(str(options.knownPath))
        js_interesting_args.append(str(options.jsEngine))
        if options.randomFlags:
            engineFlags = shell_flags.random_flag_set(options.jsEngine)  # pylint: disable=invalid-name
            js_interesting_args.extend(engineFlags)
        #js_interesting_args.extend(["-e", "maxRunTime=" + str(options.timeout * (1000 // 2))])
        #js_interesting_args.extend(["-f", fuzzjs])
        js_interesting_args.extend([fuzzjs])
        js_interesting_options = js_interesting.parseOptions(js_interesting_args)

        iteration += 1
        logPrefix = wtmpDir / ("w" + str(iteration))  # pylint: disable=invalid-name

        env = {}  # default environment will be used
        if ccoverage:
            env["GCOV_PREFIX_STRIP"] = "13"  # Assumes ccoverage build from b.f.m.o
            cov_build_path = Path(args[-2]).parent.parent.parent
            assert "cov-build" in str(cov_build_path)
            env["GCOV_PREFIX"] = str(cov_build_path)

        res = js_interesting.ShellResult(js_interesting_options,
                                         # pylint: disable=no-member
                                         js_interesting_options.jsengineWithArgs, logPrefix, False, env=env)

        if res.lev != js_interesting.JS_FINE:
            out_log = (logPrefix.parent / (logPrefix.stem + "-out")).with_suffix(".txt")
            showtail(out_log)
            err_log = (logPrefix.parent / (logPrefix.stem + "-err")).with_suffix(".txt")
            showtail(err_log)

            # splice jsfunfuzz.js with `grep "/*FRC-" wN-out`
            reduced_log = (logPrefix.parent / (logPrefix.stem + "-reduced")).with_suffix(".js")
            [before, after] = file_manipulation.fuzzSplice(fuzzjs)

            with io.open(str(out_log), "r", encoding="utf-8", errors="replace") as f:
                newfileLines = before + [  # pylint: disable=invalid-name
                    l.replace("/*FRC-", "/*") for l in file_manipulation.linesStartingWith(f, "/*FRC-")] + after
            orig_log = (logPrefix.parent / (logPrefix.stem + "-orig")).with_suffix(".js")
            with io.open(str(orig_log), "w", encoding="utf-8", errors="replace") as f:
                f.writelines(newfileLines)
            with io.open(str(reduced_log), "w", encoding="utf-8", errors="replace") as f:
                f.writelines(newfileLines)

            if not ccoverage:
                # Run Lithium and autobisectjs (make a reduced testcase and find a regression window)
                interestingpy = "funfuzz.js.js_interesting"
                itest = [interestingpy]
                if options.valgrind:
                    itest.append("--valgrind")
                itest.append("--minlevel=" + str(res.lev))
                itest.append("--timeout=" + str(options.timeout))
                itest.append(options.knownPath)
                (lithResult, _lithDetails, autoBisectLog) = lithium_helpers.pinpoint(  # pylint: disable=invalid-name
                    itest, logPrefix, options.jsEngine, engineFlags, reduced_log, options.repo,
                    options.build_options_str, targetTime, res.lev)

                # Upload with final output
                if lithResult == lithium_helpers.LITH_FINISHED:
                    # pylint: disable=no-member
                    fargs = js_interesting_options.jsengineWithArgs[:-1] + [reduced_log]
                    # pylint: disable=invalid-name
                    retestResult = js_interesting.ShellResult(js_interesting_options,
                                                              fargs,
                                                              logPrefix.parent / (logPrefix.stem + "-final"),
                                                              False)
                    if retestResult.lev > js_interesting.JS_FINE:
                        res = retestResult
                        quality = 0
                    else:
                        quality = 6
                else:
                    quality = 10

                print("Submitting %s (quality=%s) at %s" % (reduced_log, quality, time.asctime()))

                metadata = {}
                if autoBisectLog:
                    metadata = {"autoBisectLog": "".join(autoBisectLog)}
                collector.submit(res.crashInfo, str(reduced_log), quality, metaData=metadata)
                print("Submitted %s" % reduced_log)

        else:
            are_flags_deterministic = "--dump-bytecode" not in engineFlags and "-D" not in engineFlags
            # pylint: disable=no-member
            if options.use_compare_jit and res.lev == js_interesting.JS_FINE and \
                    js_interesting_options.shellIsDeterministic and are_flags_deterministic:
                out_log = (logPrefix.parent / (logPrefix.stem + "-out")).with_suffix(".txt")
                linesToCompare = jitCompareLines(out_log, "/*FCM*/")  # pylint: disable=invalid-name
                jitcomparefilename = (logPrefix.parent / (logPrefix.stem + "-cj-in")).with_suffix(".js")
                with io.open(str(jitcomparefilename), "w", encoding="utf-8", errors="replace") as f:
                    f.writelines(linesToCompare)
                if not ccoverage:
                    compare_jit.compare_jit(options.jsEngine, engineFlags, jitcomparefilename,
                                            logPrefix.parent / (logPrefix.stem + "-cj"), options.repo,
                                            options.build_options_str, targetTime, js_interesting_options)
                if jitcomparefilename.is_file():
                    jitcomparefilename.unlink()

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
    with io.open(str(jsfunfuzzOutputFilename), "r", encoding="utf-8", errors="replace") as f:
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
    many_timed_runs(None, os_ops.make_wtmp_dir(Path(os.getcwdu() if sys.version_info.major == 2 else os.getcwd())),
                    sys.argv[1:], create_collector.make_collector(), False)

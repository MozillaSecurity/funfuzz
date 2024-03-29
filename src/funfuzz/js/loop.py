# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Allows the funfuzz harness to run continuously.
"""

import argparse
import io
import json
import logging
import os
from pathlib import Path
import platform
import subprocess
import sys
from textwrap import dedent
import time
import zipfile

from . import compare_jit
from . import js_interesting
from . import link_fuzzer
from . import shell_flags
from . import with_binaryen
from ..util import create_collector
from ..util import file_manipulation
from ..util import file_system_helpers
from ..util import lithium_helpers
from ..util import os_ops


LOG = logging.getLogger("funfuzz")


def parseOpts(args):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare-jit",
                        action="store_true", dest="use_compare_jit",
                        help="After running the fuzzer, run the FCM lines against the engine "
                             "in two configurations and compare the output.")
    parser.add_argument("--random-flags",
                        action="store_true", dest="randomFlags",
                        help="Pass a random set of flags (e.g. --ion-eager) to the js engine")
    parser.add_argument("--repo", type=Path, default=Path.home() / "trees" / "mozilla-central",
                        help="The hg repository (e.g. ~/trees/mozilla-central/), for bisection")
    # if you run loop directly w/o --build, lithium_helpers.pinpoint will try to guess
    parser.add_argument("--build",
                        dest="build_options_str",
                        help="The build options, for bisection")
    parser.add_argument("--valgrind",
                        action="store_true",
                        help="use valgrind with a reasonable set of options")
    parser.add_argument("--no-fuzz-wasm", action="store_false", dest="fuzz_wasm",
                        help="Don't run the fuzzer against wasm")
    # jsfunfuzz will quit after half this time if it's not looping.
    # higher = more complex mixing, especially with regression tests.
    # lower = less time wasted in timeouts and in compare_jit testcases that are thrown away due to OOMs.
    parser.add_argument("timeout", type=int, help="kill js shell if it runs this long")
    # FIXME: We can probably remove args[1]  # pylint: disable=fixme
    parser.add_argument("unused", help="Legacy option (value ignored)")
    parser.add_argument("jsEngine", type=Path)
    parser.add_argument("engineFlags", nargs=argparse.REMAINDER)
    parser.set_defaults(knownPath="mozilla-central")
    options = parser.parse_args(args)

    if options.valgrind and options.use_compare_jit:
        print("Note: When running compare_jit, the --valgrind option will be ignored", file=sys.stderr)

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
    libdir = Path("js") / "src" / "jit-test" / "lib"
    js_src_tests_dir = Path("js") / "src" / "tests"
    non262_tests_dir = js_src_tests_dir / "non262"
    test262_tests_dir = js_src_tests_dir / "test262"
    w_pltfrm_res_dir = Path("testing") / "web-platform" / "tests" / "resources"
    return dedent(f"""
        const regressionTestsRoot = {json.dumps(str(repo) + os.sep)};
        const libdir = regressionTestsRoot + {json.dumps(str(libdir) + os.sep)}; // needed by jit-tests
        const js_src_tests_dir = regressionTestsRoot + {json.dumps(str(js_src_tests_dir) + os.sep)}; // streams tests
        const non262_tests_dir = regressionTestsRoot + {json.dumps(str(non262_tests_dir) + os.sep)}; // non262 tests
        const test262_tests_dir = regressionTestsRoot + {json.dumps(str(test262_tests_dir) + os.sep)}; // test262 tests
        const w_pltfrm_res_dir = regressionTestsRoot + {json.dumps(str(w_pltfrm_res_dir) + os.sep)}; // streams tests
        const regressionTestList = {json.dumps(inTreeRegressionTests(repo))};
    """)


def inTreeRegressionTests(repo):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    jit_tests = jsFilesIn(len(str(repo)), repo / "js" / "src" / "jit-test" / "tests")
    js_tests = jsFilesIn(len(str(repo)), repo / "js" / "src" / "tests")
    non262_tests = jsFilesIn(len(str(repo)), repo / "js" / "src" / "tests" / "non262")
    test262_tests = jsFilesIn(len(str(repo)), repo / "js" / "src" / "tests" / "test262")
    streams_tests = jsFilesIn(len(str(repo)), repo / "testing" / "web-platform" / "tests" / "streams")
    return jit_tests + js_tests + non262_tests + test262_tests + streams_tests


def jsFilesIn(repoPathLength, root):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    return [os.path.join(path, filename)[repoPathLength + 1:]
            for path, _dirs, files in os.walk(str(root))
            for filename in files
            if filename.endswith(".js")]


def get_path_prefix(shell):
    """Get build path prefix for the jsshell binary.

    Args:
        shell (Path/str): path to jsshell binary downloaded by fuzzfetch

    Returns:
        Path: pathprefix from js.fuzzmanagerconf
    """
    cfg = Path(str(shell) + ".fuzzmanagerconf")
    prefix = None
    with cfg.open() as cfg_fp:
        for line in cfg_fp:
            if line.startswith("pathprefix = "):
                prefix = Path(line.split(" = ", 1)[1].strip())
                break
    assert prefix is not None, "Path prefix not found in %s" % (str(cfg),)
    return prefix


def get_gcov_prefix_strip(shell):
    """Get GCOV_PREFIX_STRIP value for the jsshell binary.

     GCOV_PREFIX_STRIP should be the # of path components in
       js.fuzzmanagerconf "pathprefix"

    Args:
        shell (Path/str): path to jsshell binary downloaded by fuzzfetch

    Returns:
        int: GCOV_PREFIX_STRIP value
    """
    # Path.parts is a tuple of path components. Subtract 1 because it includes / or C:\
    return len(get_path_prefix(shell).parts) - 1


def many_timed_runs(target_time, wtmp_dir, args, collector, ccoverage):
    """As long as the run length duration is less than target_time, the harness will run the fuzzers in a loop.

    Args:
        target_time (int): Target time the harness runs before restarting
        wtmp_dir (Path): Path to the wtmp directory
        args (list): Extra arguments
        collector (object): Collector object for FuzzManager submission
        ccoverage (bool): Whether we are running in coverage gathering mode
    """
    # pylint: disable=too-complex,too-many-branches,too-many-locals,too-many-statements
    options = parseOpts([str(arg) for arg in args])
    startTime = time.time()  # pylint: disable=invalid-name

    if options.repo.is_dir():
        regressionTestPrologue = makeRegressionTestPrologue(options.repo)  # pylint: disable=invalid-name
    else:
        regressionTestPrologue = ""  # pylint: disable=invalid-name

    fuzzjs = wtmp_dir / "jsfunfuzz.js"

    link_fuzzer.link_fuzzer(fuzzjs, regressionTestPrologue)
    assert fuzzjs.is_file()

    env = {}  # default environment will be used
    if ccoverage:
        # Assumes ccoverage build from Taskcluster via fuzzfetch
        env["GCOV_PREFIX_STRIP"] = str(get_gcov_prefix_strip(args[-2]))
        cov_build_path = Path(args[-2]).parent.parent.parent
        assert "cov-build" in str(cov_build_path)
        env["GCOV_PREFIX"] = str(cov_build_path)
        LOG.info("collecting coverage with GCOV_PREFIX_STRIP=%s and GCOV_PREFIX=%s",
                 env["GCOV_PREFIX_STRIP"], env["GCOV_PREFIX"])

    iteration = 0
    while True:
        if target_time and time.time() > startTime + target_time:
            print("Out of time!")
            fuzzjs.unlink()
            if not os.listdir(str(wtmp_dir)):
                wtmp_dir.rmdir()
            break

        # Construct command needed to loop jsfunfuzz fuzzing.
        js_interesting_args = []
        js_interesting_args.append(f"--timeout={options.timeout}")
        if options.valgrind:
            js_interesting_args.append("--valgrind")
        js_interesting_args.append(str(options.knownPath))
        js_interesting_args.append(str(options.jsEngine))
        if options.randomFlags:
            options.engineFlags = shell_flags.random_flag_set(options.jsEngine)
            js_interesting_args.extend(options.engineFlags)
        js_interesting_args.extend(["-e", f"maxRunTime={options.timeout * (1000 // 2)}"])
        js_interesting_args.extend(["-f", fuzzjs])
        js_interesting_opts = js_interesting.parseOptions(js_interesting_args)

        iteration += 1
        log_prefix = wtmp_dir / f"w{iteration}"

        res, out_log = run_to_report(options, js_interesting_opts, env.copy(), log_prefix,
                                     fuzzjs, ccoverage, collector, target_time)

        # funbind - integrate with binaryen wasm project but only on Linux x86_64
        # (aarch64 got activated as we now first compile our own binaryen aarch64 Linux builds)
        # For binaryen Linux x86, first wait for https://github.com/WebAssembly/binaryen/issues/1615 to be fixed
        # I do not believe binaryen x86 builds are needed since all our host OS'es are 64-bit
        if options.fuzz_wasm and platform.system() == "Linux" and "64" in platform.machine() \
                and out_log.is_file() and not options.valgrind:
            run_to_report_wasm(options, js_interesting_opts, env.copy(), log_prefix,
                               out_log, ccoverage, collector, target_time)

        # pylint: disable=no-member
        if options.use_compare_jit and res.lev == js_interesting.JS_FINE and js_interesting_opts.shellIsDeterministic:
            cj_out_log = (log_prefix.parent / f"{log_prefix.stem}-out").with_suffix(".txt")
            linesToCompare = jitCompareLines(cj_out_log, "/*FCM*/")  # pylint: disable=invalid-name
            cj_testcase = (log_prefix.parent / f"{log_prefix.stem}-cj-in").with_suffix(".js")
            with io.open(str(cj_testcase), "w", encoding="utf-8", errors="replace") as f:
                f.writelines(linesToCompare)

            if "--more-compartments" in js_interesting_opts.jsengineWithArgs:
                # --more-compartments should not be tested with compare_jit, see bug 1521338 comment 7
                js_interesting_opts.jsengineWithArgs.remove("--more-compartments")
            if "--wasm-compiler=none" in js_interesting_opts.jsengineWithArgs:
                # WebAssembly object will not be present if this flag is not removed
                js_interesting_opts.jsengineWithArgs.remove("--wasm-compiler=none")

            compare_jit.compare_jit(options.jsEngine, options.engineFlags, cj_testcase,
                                    log_prefix.parent / f"{log_prefix.stem}-cj", options.repo,
                                    options.build_options_str, target_time, js_interesting_opts, ccoverage)

            if cj_testcase.is_file():
                cj_testcase.unlink()

        file_system_helpers.delete_logs(log_prefix)


def run_to_report(options, js_interesting_opts, env, log_prefix, fuzzjs, ccoverage, collector, target_time):
    """Runs the js shell with testcases and report them to FuzzManager if they are interesting.

    Args:
        options (function): Options for loop.py
        js_interesting_opts (function): Options for js_interesting.py
        env (dict): Environment to be run in
        log_prefix (str): log_prefix'es
        fuzzjs (Path): Path to the jsfunfuzz file
        ccoverage (bool): Whether we are running in coverage gathering mode
        collector (object): Collector object for FuzzManager submission
        target_time (int): Target time the harness runs before restarting

    Returns:
        Tuple: Returns a tuple of the results object, Path to the stdout and stderr logs, and Path to the
               reduced testcase
    """
    # pylint: disable=too-many-arguments,too-many-locals
    res = js_interesting.ShellResult(js_interesting_opts,
                                     js_interesting_opts.jsengineWithArgs, log_prefix, False, env=env)

    out_log = (log_prefix.parent / f"{log_prefix.stem}-out").with_suffix(".txt")
    err_log = (log_prefix.parent / f"{log_prefix.stem}-err").with_suffix(".txt")
    reduced_log = (log_prefix.parent / f"{log_prefix.stem}-reduced").with_suffix(".js")

    if res.lev >= js_interesting.JS_OVERALL_MISMATCH:
        showtail(out_log)
        showtail(err_log)

        # splice jsfunfuzz.js with `grep "/*FRC-" wN-out`
        [before, after] = file_manipulation.fuzzSplice(fuzzjs)

        with io.open(str(out_log), "r", encoding="utf-8", errors="replace") as f:
            newfileLines = before + [  # pylint: disable=invalid-name
                l.replace("/*FRC-", "/*") for l in file_manipulation.linesStartingWith(f, "/*FRC-")] + after
        orig_log = (log_prefix.parent / f"{log_prefix.stem}-orig").with_suffix(".js")
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
            itest.append(f"--minlevel={res.lev}")
            itest.append(f"--timeout={options.timeout}")
            itest.append(options.knownPath)
            (lith_result, _lith_details, autobisect_log) = lithium_helpers.pinpoint(
                itest, log_prefix, options.jsEngine, options.engineFlags, reduced_log, options.repo,
                options.build_options_str, target_time, res.lev)

            # Upload with final output
            if lith_result == lithium_helpers.LITH_FINISHED:
                fargs = js_interesting_opts.jsengineWithArgs[:-1] + [reduced_log]
                retest_result = js_interesting.ShellResult(js_interesting_opts,
                                                           fargs,
                                                           log_prefix.parent / f"{log_prefix.stem}-final",
                                                           False)
                if retest_result.lev > js_interesting.JS_FINE:
                    res = retest_result
                    quality = 0
                else:
                    quality = 6
            else:
                quality = 10

            print(f"Submitting {reduced_log} (quality={quality}) at {time.asctime()}")

            metadata = {}
            if autobisect_log:
                metadata = {"autobisect_log": "".join(autobisect_log)}

            # Create .zip file for uploading to FuzzManager as some testcases can be 8MB+, see https://git.io/fjqxI
            assert reduced_log.is_file()
            result_zip = log_prefix.parent / "reduced.zip"
            with zipfile.ZipFile(result_zip, "w") as f:
                f.write(reduced_log, reduced_log.name, compress_type=zipfile.ZIP_DEFLATED)

            create_collector.submit_collector(collector, res.crashInfo, str(result_zip), quality, meta_data=metadata)
            print(f"Submitted {result_zip}")

    return res, out_log


def run_to_report_wasm(_options, js_interesting_opts, env, log_prefix, out_log, ccoverage, collector, _target_time):
    """Runs the js shell with wasm testcases and report them to FuzzManager if they are interesting.

    Args:
        _options (function): Options for loop.py
        js_interesting_opts (function): Options for js_interesting.py
        env (dict): Environment to be run in
        log_prefix (str): log_prefix'es
        out_log (Path): Path to the jsfunfuzz w*-out log file to act as the seed
        ccoverage (bool): Whether we are running in coverage gathering mode
        collector (object): Collector object for FuzzManager submission
        _target_time (int): Target time the harness runs before restarting
    """
    # pylint: disable=too-many-arguments
    log_prefix = (log_prefix.parent / f"{log_prefix.stem}-wasm")

    # Use the generated out_log as the seed for binaryen
    wrapper_file, wasm_file = with_binaryen.wasmopt_run(out_log)
    # We remove the last two entries of jsengineWithArgs (-f and the original filename)
    # wasm files need to have -f absent
    js_interesting_opts.jsengineWithArgs = js_interesting_opts.jsengineWithArgs[:-2] + [str(wrapper_file),
                                                                                        str(wasm_file)]
    # Ensure ion flags such as --execute="setJitCompilerOption(\"ion.forceinlineCaches\",1)" are not executed
    # for wasm files
    execute_ion_flags_in_shell = False
    for runtime_flag in js_interesting_opts.jsengineWithArgs:
        if "--execute=" in str(runtime_flag) and "ion." in str(runtime_flag):
            execute_ion_flags_in_shell = True

    if not execute_ion_flags_in_shell:
        res = js_interesting.ShellResult(js_interesting_opts,
                                         js_interesting_opts.jsengineWithArgs, log_prefix, False, env=env)

        if res.lev >= js_interesting.JS_OVERALL_MISMATCH:
            wasm_out_log = (log_prefix.parent / f"{log_prefix.stem}-out").with_suffix(".txt")
            showtail(wasm_out_log)  # wasm_out_log appears again after js_interesting.ShellResult is run
            wasm_err_log = (log_prefix.parent / f"{log_prefix.stem}-err").with_suffix(".txt")
            showtail(wasm_err_log)

            # binaryen integration, we do not yet have pinpoint nor autobisectjs support, so temporarily quality 10
            assert wrapper_file.is_file()
            result_zip = log_prefix.parent / "reduced.zip"
            with zipfile.ZipFile(result_zip, "w") as f:
                f.write(out_log, f"{out_log.name}-binaryen-v{with_binaryen.BINARYEN_VERSION}-seed",
                        compress_type=zipfile.ZIP_DEFLATED)
                f.write(wrapper_file, wrapper_file.name, compress_type=zipfile.ZIP_DEFLATED)
                f.write(wasm_file, wasm_file.name, compress_type=zipfile.ZIP_DEFLATED)

            if not ccoverage:
                # Quality is 10, meta_data {}
                create_collector.submit_collector(collector, res.crashInfo, str(result_zip), 10, meta_data={})
                print(f"Submitted {result_zip}")


def jitCompareLines(jsfunfuzzOutputFilename, marker):  # pylint: disable=invalid-name,missing-param-doc
    # pylint: disable=missing-return-doc,missing-return-type-doc,missing-type-doc
    """Create a compare_jit file, using the lines marked by jsfunfuzz as valid for comparison."""
    lines = [
        "addMarkObservers = function() { };\n",
        "backtrace = function() { };\n",
        "clearMarkObservers = function() { };\n",
        "dumpHeap = function() { };\n",
        "dumpObject = function() { };\n",
        "dumpScopeChain = function() { };\n",
        "dumpStringRepresentation = function() { };\n",
        "evalInCooperativeThread = function() { };\n",
        "evalInWorker = function() { };\n",
        "getBacktrace = function() { };\n",
        "getLcovInfo = function() { };\n",
        "getMarks = function() { };\n",
        "isAsmJSCompilationAvailable = function() { };\n",
        "monitorType = function() { };\n",
        "nukeAllCCWs = function() { };\n",
        "Object.getOwnPropertyNames = function() { };\n",
        "Object.getOwnPropertyDescriptors = function() { };\n",
        "offThreadCompileScript = function() { };\n",
        "oomTest = function() { };\n",
        "printProfilerEvents = function() { };\n",
        "saveStack = function() { };\n",
        "wasmIsSupported = function() { return true; };\n",
        "// DDBEGIN\n",
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
        "// DDEND\n",
    ]
    return lines


if __name__ == "__main__":
    many_timed_runs(None, os_ops.make_wtmp_dir(Path(os.getcwd())),
                    sys.argv[1:], create_collector.make_collector(), False)

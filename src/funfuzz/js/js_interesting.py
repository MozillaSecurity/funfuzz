# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Check whether a testcase causes an interesting result in a shell.
"""

import io
from optparse import OptionParser  # pylint: disable=deprecated-module
import os
from pathlib import Path
import platform
from shlex import quote
import shutil
import subprocess
import sys

from FTB.ProgramConfiguration import ProgramConfiguration
import FTB.Signatures.CrashInfo as Crash_Info
import lithium.interestingness.timed_run as timedrun

from . import inspect_shell
from ..util import create_collector
from ..util import file_manipulation
from ..util import os_ops
from ..util.logging_helpers import get_logger

LOG_JS_INTERESTING = get_logger(__name__)

# Levels of unhappiness.
# These are in order from "most expected to least expected" rather than "most ok to worst".
# Fuzzing will note the level, and pass it to Lithium.
# Lithium is allowed to go to a higher level.
JS_LEVELS = 6
JS_LEVEL_NAMES = [
    "fine",
    "jsfunfuzz did not finish",
    "jsfunfuzz decided to exit",
    "overall mismatch",
    "valgrind error",
    "new assert or crash",
]
assert len(JS_LEVEL_NAMES) == JS_LEVELS
(
    JS_FINE,
    JS_DID_NOT_FINISH,                  # correctness (only jsfunfuzzLevel)
    JS_DECIDED_TO_EXIT,                 # correctness (only jsfunfuzzLevel)
    JS_OVERALL_MISMATCH,                # correctness (only compare_jit)
    JS_VG_AMISS,                        # memory safety
    JS_NEW_ASSERT_OR_CRASH,             # memory safety or other issue that is definitely a bug
) = range(JS_LEVELS)


gOptions = ""  # pylint: disable=invalid-name
VALGRIND_ERROR_EXIT_CODE = 77


class ShellResult:  # pylint: disable=missing-docstring,too-many-instance-attributes,too-few-public-methods
    # options dict should include: timeout, knownPath, collector, valgrind, shellIsDeterministic
    def __init__(self, options, runthis, logPrefix, in_compare_jit, env=None):  # pylint: disable=too-complex
        # pylint: disable=too-many-arguments,too-many-branches,too-many-locals,too-many-statements

        # If Lithium uses this as an interestingness test, logPrefix is likely not a Path object, so make it one.
        logPrefix = Path(logPrefix)
        pathToBinary = runthis[0].expanduser().resolve()  # pylint: disable=invalid-name
        # This relies on the shell being a local one from compile_shell:
        # Ignore trailing ".exe" in Win, also abspath makes it work w/relative paths like "./js"
        # pylint: disable=invalid-name
        assert pathToBinary.with_suffix(".fuzzmanagerconf").is_file()
        pc = ProgramConfiguration.fromBinary(str(pathToBinary.parent / pathToBinary.stem))
        pc.addProgramArguments(runthis[1:-1])

        if options.valgrind:
            runthis = (
                inspect_shell.constructVgCmdList(errorCode=VALGRIND_ERROR_EXIT_CODE) +
                [f"--suppressions={filename}" for filename in "valgrind_suppressions.txt"] +
                runthis)

        timed_run_kw = {"env": (env or os.environ)}
        if not (platform.system() == "Windows" or
                # We cannot set a limit for RLIMIT_AS for ASan binaries
                inspect_shell.queryBuildConfiguration(options.jsengine, "asan")):
            timed_run_kw["preexec_fn"] = set_ulimit

        lithium_logPrefix = str(logPrefix).encode("utf-8")
        if isinstance(lithium_logPrefix, b"".__class__):
            lithium_logPrefix = lithium_logPrefix.decode("utf-8", errors="replace")

        # logPrefix should be a string for timed_run in Lithium version 0.2.1 to work properly, apparently
        runinfo = timedrun.timed_run(
            [str(x) for x in runthis],  # Convert all Paths/bytes to strings for Lithium
            options.timeout,
            lithium_logPrefix,
            **timed_run_kw)

        lev = JS_FINE
        issues = []
        auxCrashData = []  # pylint: disable=invalid-name

        # FuzzManager expects a list of strings rather than an iterable, so bite the
        # bullet and "readlines" everything into memory.
        out_log = (logPrefix.parent / f"{logPrefix.stem}-out").with_suffix(".txt")
        with io.open(str(out_log), "r", encoding="utf-8", errors="replace") as f:
            out = f.readlines()
        err_log = (logPrefix.parent / f"{logPrefix.stem}-err").with_suffix(".txt")
        with io.open(str(err_log), "r", encoding="utf-8", errors="replace") as f:
            err = f.readlines()

        if options.valgrind and runinfo.return_code == VALGRIND_ERROR_EXIT_CODE:
            issues.append("valgrind reported an error")
            lev = max(lev, JS_VG_AMISS)
            valgrindErrorPrefix = f"=={runinfo.pid}=="
            for line in err:
                if valgrindErrorPrefix and valgrindErrorPrefix in line:
                    issues.append(line.rstrip())
        elif runinfo.sta == timedrun.CRASHED:
            if os_ops.grab_crash_log(runthis[0], runinfo.pid, logPrefix, True):
                crash_log = (logPrefix.parent / f"{logPrefix.stem}-crash").with_suffix(".txt")
                with io.open(str(crash_log), "r", encoding="utf-8", errors="replace") as f:
                    auxCrashData = [line.strip() for line in f.readlines()]
        elif file_manipulation.amiss(logPrefix):
            issues.append("malloc error")
            lev = max(lev, JS_NEW_ASSERT_OR_CRASH)
        elif runinfo.return_code == 0 and not in_compare_jit:
            # We might have(??) run jsfunfuzz directly, so check for special kinds of bugs
            for line in out:
                if "Found a bug: " in line and not ("NestTest" in line and oomed(err)):
                    lev = JS_DECIDED_TO_EXIT
                    issues.append(line.rstrip())
            if options.shellIsDeterministic and not understoodJsfunfuzzExit(out, err) and not oomed(err):
                issues.append("jsfunfuzz didn't finish")
                lev = JS_DID_NOT_FINISH

        # Copy non-crash issues to where FuzzManager's "AssertionHelper" can see it.
        if lev != JS_FINE:
            for issue in issues:
                err.append(f"[Non-crash bug] {issue}")

        activated = False  # Turn on when trying to report *reliable* testcases that do not have a coredump
        # On Linux, fall back to run testcase via gdb using --args if core file data is unavailable
        # Note that this second round of running uses a different fuzzSeed as the initial if default jsfunfuzz is run
        # We should separate this out, i.e. running jsfunfuzz within a debugger, only if core dumps cannot be generated
        if (activated and platform.system() == "Linux" and
                shutil.which("gdb") and not auxCrashData and not in_compare_jit):
            LOG_JS_INTERESTING.info("No core file found on Linux - falling back to run via gdb")
            extracted_gdb_cmds = ["-ex", "run"]
            with io.open(str(Path(__file__).parent.parent / "util" / "gdb_cmds.txt"), "r",
                         encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.rstrip() and "#" not in line and "echo" not in line:
                        extracted_gdb_cmds.append("-ex")
                        extracted_gdb_cmds.append(f"{line.rstrip()}")
            no_main_log_gdb_log = subprocess.run(
                (["gdb", "-n", "-batch"] + extracted_gdb_cmds + ["--args"] +
                 [str(x) for x in runthis]),
                check=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
            auxCrashData = no_main_log_gdb_log.stdout

        # Finally, make a CrashInfo object and parse stack traces for asan/crash/assertion bugs
        crashInfo = Crash_Info.CrashInfo.fromRawCrashData(out, err, pc, auxCrashData=auxCrashData)

        create_collector.printCrashInfo(crashInfo)
        # We only care about crashes and assertion failures on shells with no symbols
        # Note that looking out for the Assertion failure message is highly SpiderMonkey-specific
        if not isinstance(crashInfo, Crash_Info.NoCrashInfo) or \
                "Assertion failure: " in str(crashInfo.rawStderr) or \
                "Segmentation fault" in str(crashInfo.rawStderr) or \
                "Bus error" in str(crashInfo.rawStderr):
            lev = max(lev, JS_NEW_ASSERT_OR_CRASH)

        try:
            match = options.collector.search(crashInfo)
            if match[0] is not None:
                create_collector.printMatchingSignature(match)
                lev = JS_FINE
        except UnicodeDecodeError:  # Sometimes FM throws due to unicode issues
            LOG_JS_INTERESTING.warning("FuzzManager is throwing a UnicodeDecodeError, signature matching skipped")
            match = False

        LOG_JS_INTERESTING.info("%s | %s", logPrefix, summaryString(issues, lev, runinfo.elapsedtime))

        if lev != JS_FINE:
            summary_log = (logPrefix.parent / f"{logPrefix.stem}-summary").with_suffix(".txt")
            with io.open(str(summary_log), "w", encoding="utf-8", errors="replace") as f:
                f.writelines([f"Number: {logPrefix}\n",
                              f'Command: {" ".join(quote(str(x)) for x in runthis)}\n'] +
                             [f"Status: {i}\n" for i in issues])

        self.lev = lev
        self.out = out
        self.err = err
        self.issues = issues
        self.crashInfo = crashInfo  # pylint: disable=invalid-name
        self.match = match
        self.runinfo = runinfo
        self.return_code = runinfo.return_code


def understoodJsfunfuzzExit(out, err):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    for line in err:
        if "terminate called" in line or "quit called" in line:
            return True
        if "can't allocate region" in line:
            return True

    for line in out:
        # Note that "jsfunfuzz broke its own scripting environment: " is not currently generated in error-reporting.js
        if line.startswith("It's looking good!") or line.startswith("jsfunfuzz broke its own scripting environment: "):
            return True
        if "Found a bug: " in line:
            return True
        if line.startswith("[fuzz-exec] calling "):  # Working wasm testcases show this in stdout
            return True

    return False


def hitMemoryLimit(err):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc,missing-return-type-doc
    # pylint: disable=missing-type-doc
    """Return True iff stderr text indicates that the shell hit a memory limit."""
    if "ReportOverRecursed called" in err:  # pylint: disable=no-else-return
        # --enable-more-deterministic
        return "ReportOverRecursed called"
    elif "ReportOutOfMemory called" in err:
        # --enable-more-deterministic
        return "ReportOutOfMemory called"
    elif "failed to allocate" in err:
        # ASan
        return "failed to allocate"
    elif "can't allocate region" in err:
        # malloc
        return "can't allocate region"

    return None


def oomed(err):  # pylint: disable=missing-docstring,missing-return-doc,missing-return-type-doc
    # spidermonkey shells compiled with --enable-more-deterministic will tell us on stderr if they run out of memory
    for line in err:
        if hitMemoryLimit(line):
            return True
    return False


def summaryString(issues, level, elapsedtime):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    amissDetails = "" if (not issues) else f" | {issues[:5]!r} "  # pylint: disable=invalid-name
    return f"{elapsedtime:5.1f}s | {level} | {JS_LEVEL_NAMES[level]}{amissDetails}"


def truncateFile(fn, maxSize):  # pylint: disable=invalid-name,missing-docstring
    if fn.is_file() and fn.stat().st_size > maxSize:
        with io.open(str(fn), "r+", encoding="utf-8", errors="replace") as f:
            f.truncate(maxSize)


def set_ulimit():
    """Sets appropriate resource limits for the JS shell when on POSIX."""
    try:
        import resource  # pylint: disable=import-error

        # log.debug("Limit address space to 4GB")
        # This has to be twice the 2GB figure in:
        # https://hg.mozilla.org/mozilla-central/annotate/7beb238a0ea0/js/src/jit/ProcessExecutableMemory.h#l26
        # i.e. https://hg.mozilla.org/mozilla-central/rev/7beb238a0ea0 (bug 1542292) changed from 1GB to 2GB, so our
        # number here in this file has to be changed from 2GB to 4GB or else the harness (m-err.txt) will show this:
        # JS_Init failed: js::jit::InitProcessExecutableMemory() failed
        # We cannot set a limit for RLIMIT_AS for ASan binaries
        giga_byte = 2**30
        resource.setrlimit(resource.RLIMIT_AS, (4 * giga_byte, 4 * giga_byte))  # pylint: disable=no-member

        # log.debug("Limit corefiles to 0.5 GB")
        half_giga_byte = int(giga_byte // 2)
        resource.setrlimit(resource.RLIMIT_CORE, (half_giga_byte, half_giga_byte))  # pylint: disable=no-member
    except ImportError:
        # log.debug("Skipping resource import as a non-POSIX platform was detected: %s", platform.system())
        return


def parseOptions(args):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    parser = OptionParser()
    parser.disable_interspersed_args()
    parser.add_option("--valgrind",
                      action="store_true", dest="valgrind",
                      default=False,
                      help="use valgrind with a reasonable set of options")
    parser.add_option("--submit",
                      action="store_true", dest="submit",
                      default=False,
                      help="submit to fuzzmanager (if interesting)")
    parser.add_option("--minlevel",
                      type="int", dest="minimumInterestingLevel",
                      default=JS_FINE + 1,
                      help="minimum js/js_interesting level for lithium to consider the testcase interesting")
    parser.add_option("--timeout",
                      type="int", dest="timeout",
                      default=120,
                      help="timeout in seconds")
    options, args = parser.parse_args(args)
    if len(args) < 2:
        raise Exception("Not enough positional arguments")
    options.knownPath = args[0]
    options.jsengineWithArgs = [Path(args[1]).resolve()] + args[2:-1] + [Path(args[-1]).resolve()]
    options.jsengine = options.jsengineWithArgs[0]  # options.jsengine is needed as it is present in compare_jit
    assert options.jsengine.is_file()  # js shell
    assert options.jsengineWithArgs[-1].is_file()  # testcase
    options.collector = create_collector.make_collector()
    options.shellIsDeterministic = inspect_shell.queryBuildConfiguration(
        options.jsengine, "more-deterministic")

    return options


# loop uses parseOptions and ShellResult [with in_compare_jit = False]
# compare_jit uses ShellResult [with in_compare_jit = True]

# For use by Lithium and autobisectjs. (autobisectjs calls init multiple times because it changes the js engine name)
def init(args):  # pylint: disable=missing-docstring
    global gOptions  # pylint: disable=global-statement,invalid-name
    gOptions = parseOptions(args)


# FIXME: _args is unused here, we should check if it can be removed?  # pylint: disable=fixme
def interesting(_args, cwd_prefix):  # pylint: disable=missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    cwd_prefix = Path(cwd_prefix)  # Lithium uses this function and cwd_prefix from Lithium is not a Path
    options = gOptions
    # options, runthis, logPrefix, in_compare_jit
    res = ShellResult(options, options.jsengineWithArgs, cwd_prefix, False)
    out_log = (cwd_prefix.parent / f"{cwd_prefix.stem}-out").with_suffix(".txt")
    err_log = (cwd_prefix.parent / f"{cwd_prefix.stem}-err").with_suffix(".txt")
    truncateFile(out_log, 1000000)
    truncateFile(err_log, 1000000)
    return res.lev >= gOptions.minimumInterestingLevel


# For direct, manual use
def main():  # pylint: disable=missing-docstring
    options = parseOptions(sys.argv[1:])
    cwd_prefix = Path.cwd() / "m"
    res = ShellResult(options, options.jsengineWithArgs, cwd_prefix, False)  # pylint: disable=no-member
    LOG_JS_INTERESTING.info(res.lev)
    if options.submit:  # pylint: disable=no-member
        if res.lev >= options.minimumInterestingLevel:  # pylint: disable=no-member
            testcaseFilename = options.jsengineWithArgs[-1]  # pylint: disable=invalid-name,no-member
            LOG_JS_INTERESTING.info("Submitting %s", testcaseFilename)
            quality = 0
            # pylint: disable=no-member
            create_collector.submit_collector(options.collector, res.crashInfo, str(testcaseFilename), quality)
        else:
            LOG_JS_INTERESTING.info("Not submitting (not interesting)")


if __name__ == "__main__":
    main()

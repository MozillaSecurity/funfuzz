# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Check whether a testcase causes an interesting result in a shell.
"""

from __future__ import absolute_import, print_function  # isort:skip

from optparse import OptionParser  # pylint: disable=deprecated-module
import os
import sys

# These pylint errors exist because FuzzManager is not Python 3-compatible yet
from FTB.ProgramConfiguration import ProgramConfiguration  # pylint: disable=import-error
import FTB.Signatures.CrashInfo as CrashInfo  # pylint: disable=import-error,no-name-in-module
import lithium.interestingness.timed_run as timed_run
from past.builtins import range  # pylint: disable=redefined-builtin
from shellescape import quote

from . import inspect_shell
from ..util import create_collector
from ..util import detect_malloc_errors
from ..util import subprocesses as sps

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
    "new assert or crash"
]
assert len(JS_LEVEL_NAMES) == JS_LEVELS
(
    JS_FINE,
    JS_DID_NOT_FINISH,                  # correctness (only jsfunfuzzLevel)
    JS_DECIDED_TO_EXIT,                 # correctness (only jsfunfuzzLevel)
    JS_OVERALL_MISMATCH,                # correctness (only compare_jit)
    JS_VG_AMISS,                        # memory safety
    JS_NEW_ASSERT_OR_CRASH              # memory safety or other issue that is definitely a bug
) = range(JS_LEVELS)


gOptions = ""  # pylint: disable=invalid-name
VALGRIND_ERROR_EXIT_CODE = 77


class ShellResult(object):  # pylint: disable=missing-docstring,too-many-instance-attributes,too-few-public-methods

    # options dict should include: timeout, knownPath, collector, valgrind, shellIsDeterministic
    def __init__(self, options, runthis, logPrefix, in_compare_jit):  # pylint: disable=too-complex,too-many-branches
        # pylint: disable=too-many-locals,too-many-statements
        pathToBinary = runthis[0]  # pylint: disable=invalid-name
        # This relies on the shell being a local one from compile_shell:
        # Ignore trailing ".exe" in Win, also abspath makes it work w/relative paths like "./js"
        # pylint: disable=invalid-name
        assert os.path.isfile(os.path.abspath(pathToBinary + ".fuzzmanagerconf"))
        pc = ProgramConfiguration.fromBinary(os.path.abspath(pathToBinary).split(".")[0])
        pc.addProgramArguments(runthis[1:-1])

        if options.valgrind:
            runthis = (
                inspect_shell.constructVgCmdList(errorCode=VALGRIND_ERROR_EXIT_CODE) +
                valgrindSuppressions() +
                runthis)

        preexec_fn = ulimitSet if os.name == "posix" else None
        # logPrefix should be a string for timed_run in Lithium version 0.2.1 to work properly, apparently
        runinfo = timed_run.timed_run(runthis, options.timeout, logPrefix.encode("utf-8"), preexec_fn=preexec_fn)

        lev = JS_FINE
        issues = []
        auxCrashData = []  # pylint: disable=invalid-name

        # FuzzManager expects a list of strings rather than an iterable, so bite the
        # bullet and "readlines" everything into memory.
        with open(logPrefix + "-out.txt") as f:
            out = f.readlines()
        with open(logPrefix + "-err.txt") as f:
            err = f.readlines()

        if options.valgrind and runinfo.return_code == VALGRIND_ERROR_EXIT_CODE:
            issues.append("valgrind reported an error")
            lev = max(lev, JS_VG_AMISS)
            valgrindErrorPrefix = "==" + str(runinfo.pid) + "=="
            for line in err:
                if valgrindErrorPrefix and line.startswith(valgrindErrorPrefix):
                    issues.append(line.rstrip())
        elif runinfo.sta == timed_run.CRASHED:
            if sps.grabCrashLog(runthis[0], runinfo.pid, logPrefix, True):
                with open(logPrefix + "-crash.txt") as f:
                    auxCrashData = [line.strip() for line in f.readlines()]
        elif detect_malloc_errors.amiss(logPrefix):
            issues.append("malloc error")
            lev = max(lev, JS_NEW_ASSERT_OR_CRASH)
        elif runinfo.return_code == 0 and not in_compare_jit:
            # We might have(??) run jsfunfuzz directly, so check for special kinds of bugs
            for line in out:
                if line.startswith("Found a bug: ") and not ("NestTest" in line and oomed(err)):
                    lev = JS_DECIDED_TO_EXIT
                    issues.append(line.rstrip())
            if options.shellIsDeterministic and not understoodJsfunfuzzExit(out, err) and not oomed(err):
                issues.append("jsfunfuzz didn't finish")
                lev = JS_DID_NOT_FINISH

        # Copy non-crash issues to where FuzzManager's "AssertionHelper" can see it.
        if lev != JS_FINE:
            for issue in issues:
                err.append("[Non-crash bug] " + issue)

        # Finally, make a CrashInfo object and parse stack traces for asan/crash/assertion bugs
        crashInfo = CrashInfo.CrashInfo.fromRawCrashData(out, err, pc, auxCrashData=auxCrashData)

        create_collector.printCrashInfo(crashInfo)
        # We only care about crashes and assertion failures on shells with no symbols
        # Note that looking out for the Assertion failure message is highly SpiderMonkey-specific
        if not isinstance(crashInfo, CrashInfo.NoCrashInfo) or \
                "Assertion failure: " in str(crashInfo.rawStderr) or \
                "Segmentation fault" in str(crashInfo.rawStderr) or \
                "Bus error" in str(crashInfo.rawStderr):
            lev = max(lev, JS_NEW_ASSERT_OR_CRASH)

        match = options.collector.search(crashInfo)
        if match[0] is not None:
            create_collector.printMatchingSignature(match)
            lev = JS_FINE

        print("%s | %s" % (logPrefix, summaryString(issues, lev, runinfo.elapsedtime)))

        if lev != JS_FINE:
            with open(logPrefix + "-summary.txt", "w") as f:
                f.writelines(["Number: " + logPrefix + "\n",
                              "Command: " + " ".join(quote(x) for x in runthis) + "\n"] +
                             ["Status: " + i + "\n" for i in issues])

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
        if line.startswith("It's looking good!") or line.startswith("jsfunfuzz broke its own scripting environment: "):
            return True
        if line.startswith("Found a bug: "):
            return True

    return False


def hitMemoryLimit(err):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc,missing-return-type-doc
    # pylint: disable=missing-type-doc
    """Return True iff stderr text indicates that the shell hit a memory limit."""
    if "ReportOverRecursed called" in err:
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


def oomed(err):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    # spidermonkey shells compiled with --enable-more-deterministic will tell us on stderr if they run out of memory
    for line in err:
        if hitMemoryLimit(line):
            return True
    return False


def summaryString(issues, level, elapsedtime):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    amissDetails = ("") if (not issues) else (" | " + repr(issues[:5]) + " ")  # pylint: disable=invalid-name
    return "%5.1fs | %d | %s%s" % (elapsedtime, level, JS_LEVEL_NAMES[level], amissDetails)


def truncateFile(fn, maxSize):  # pylint: disable=invalid-name,missing-docstring
    if os.path.exists(fn) and os.path.getsize(fn) > maxSize:
        with open(fn, "r+") as f:
            f.truncate(maxSize)


def valgrindSuppressions():  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    return ["--suppressions=" + filename for filename in "valgrind_suppressions.txt"]


def deleteLogs(logPrefix):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc
    """Whoever might call baseLevel should eventually call this function (unless a bug was found)."""
    # If this turns up a WindowsError on Windows, remember to have excluded fuzzing locations in
    # the search indexer, anti-virus realtime protection and backup applications.
    os.remove(logPrefix + "-out.txt")
    os.remove(logPrefix + "-err.txt")
    if os.path.exists(logPrefix + "-crash.txt"):
        os.remove(logPrefix + "-crash.txt")
    if os.path.exists(logPrefix + "-vg.xml"):
        os.remove(logPrefix + "-vg.xml")
    # pylint: disable=fixme
    # FIXME: in some cases, subprocesses gzips a core file only for us to delete it immediately.
    if os.path.exists(logPrefix + "-core.gz"):
        os.remove(logPrefix + "-core.gz")


def ulimitSet():  # pylint: disable=invalid-name
    """When called as a preexec_fn, sets appropriate resource limits for the JS shell. Must only be called on POSIX."""
    # module only available on POSIX
    import resource  # pylint: disable=import-error

    # Limit address space to 2GB (or 1GB on ARM boards such as ODROID).
    GB = 2**30  # pylint: disable=invalid-name
    resource.setrlimit(resource.RLIMIT_AS, (2 * GB, 2 * GB))

    # Limit corefiles to 0.5 GB.
    halfGB = int(GB // 2)  # pylint: disable=invalid-name
    resource.setrlimit(resource.RLIMIT_CORE, (halfGB, halfGB))


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
    options.jsengineWithArgs = args[1:]
    options.collector = create_collector.createCollector("jsfunfuzz")
    if not os.path.exists(options.jsengineWithArgs[0]):
        raise Exception("js shell does not exist: " + options.jsengineWithArgs[0])
    options.shellIsDeterministic = inspect_shell.queryBuildConfiguration(
        options.jsengineWithArgs[0], "more-deterministic")

    return options


# loop uses parseOptions and ShellResult [with in_compare_jit = False]
# compare_jit uses ShellResult [with in_compare_jit = True]

# For use by Lithium and autobisectjs. (autobisectjs calls init multiple times because it changes the js engine name)
def init(args):  # pylint: disable=missing-docstring
    global gOptions  # pylint: disable=global-statement,invalid-name
    gOptions = parseOptions(args)


# FIXME: _args is unused here, we should check if it can be removed?  # pylint: disable=fixme
def interesting(_args, tempPrefix):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    options = gOptions
    # options, runthis, logPrefix, in_compare_jit
    res = ShellResult(options, options.jsengineWithArgs, tempPrefix, False)
    truncateFile(tempPrefix + "-out.txt", 1000000)
    truncateFile(tempPrefix + "-err.txt", 1000000)
    return res.lev >= gOptions.minimumInterestingLevel


# For direct, manual use
def main():  # pylint: disable=missing-docstring
    options = parseOptions(sys.argv[1:])
    tempPrefix = "m"  # pylint: disable=invalid-name
    res = ShellResult(options, options.jsengineWithArgs, tempPrefix, False)  # pylint: disable=no-member
    print(res.lev)
    if options.submit:  # pylint: disable=no-member
        if res.lev >= options.minimumInterestingLevel:  # pylint: disable=no-member
            testcaseFilename = options.jsengineWithArgs[-1]  # pylint: disable=invalid-name,no-member
            print("Submitting %s" % testcaseFilename)
            quality = 0
            options.collector.submit(res.crashInfo, testcaseFilename, quality)  # pylint: disable=no-member
        else:
            print("Not submitting (not interesting)")


if __name__ == "__main__":
    main()

# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""autobisectjs, for bisecting changeset regression windows. Supports Mercurial repositories and SpiderMonkey only.
"""

from __future__ import absolute_import, unicode_literals  # isort:skip

from optparse import OptionParser  # pylint: disable=deprecated-module
import os
import re
import shutil
import sys
import tempfile
import time

from backports.print_function import print_
from lithium.interestingness.utils import rel_or_abs_import

from . import known_broken_earliest_working as kbew
from ..js import build_options
from ..js import compile_shell
from ..js import inspect_shell
from ..util import hg_helpers
from ..util import s3cache
from ..util import sm_compile_helpers
from ..util import subprocesses as sps
from ..util.lock_dir import LockDir

if sys.version_info.major == 2:
    from pathlib2 import Path  # pylint: disable=import-error
    if os.name == "posix":
        import subprocess32 as subprocess  # pylint: disable=import-error
else:
    from pathlib import Path  # pylint: disable=import-error
    import subprocess


def parseOpts():  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    # pylint: disable=too-many-branches,too-complex,too-many-statements
    usage = "Usage: %prog [options]"
    parser = OptionParser(usage)
    # http://docs.python.org/library/optparse.html#optparse.OptionParser.disable_interspersed_args
    parser.disable_interspersed_args()

    parser.set_defaults(
        resetRepoFirst=False,
        startRepo=None,
        endRepo="default",
        testInitialRevs=True,
        output="",
        watchExitCode=None,
        useInterestingnessTests=False,
        parameters="-e 42",  # http://en.wikipedia.org/wiki/The_Hitchhiker%27s_Guide_to_the_Galaxy
        compilationFailedLabel="skip",
        build_options="",
        useTreeherderBinaries=False,
        nameOfTreeherderBranch="mozilla-inbound",
    )

    # Specify how the shell will be built.
    parser.add_option("-b", "--build",
                      dest="build_options",
                      help='Specify js shell build options, e.g. -b "--enable-debug --32"'
                           "(python -m funfuzz.js.build_options --help)")

    parser.add_option("--resetToTipFirst", dest="resetRepoFirst",
                      action="store_true",
                      help="First reset to default tip overwriting all local changes. "
                           'Equivalent to first executing `hg update -C default`. Defaults to "%default".')

    # Specify the revisions between which to bisect.
    parser.add_option("-s", "--startRev", dest="startRepo",
                      help='Earliest changeset/build numeric ID to consider (usually a "good" cset). '
                           "Defaults to the earliest revision known to work at all/available.")
    parser.add_option("-e", "--endRev", dest="endRepo",
                      help='Latest changeset/build numeric ID to consider (usually a "bad" cset). '
                           'Defaults to the head of the main branch, "default", or latest available build.')
    parser.add_option("-k", "--skipInitialRevs", dest="testInitialRevs",
                      action="store_false",
                      help="Skip testing the -s and -e revisions and automatically trust them as -g and -b.")

    # Specify the type of failure to look for.
    # (Optional -- by default, internalTestAndLabel will look for exit codes that indicate a crash or assert.)
    parser.add_option("-o", "--output", dest="output",
                      help='Stdout or stderr output to be observed. Defaults to "%default". '
                           'For assertions, set to "ssertion fail"')
    parser.add_option("-w", "--watchExitCode", dest="watchExitCode",
                      type="int",
                      help='Look out for a specific exit code. Only this exit code will be considered "bad".')
    parser.add_option("-i", "--useInterestingnessTests",
                      dest="useInterestingnessTests",
                      action="store_true",
                      help="Interpret the final arguments as an interestingness test.")

    # Specify parameters for the js shell.
    parser.add_option("-p", "--parameters", dest="parameters",
                      help='Specify parameters for the js shell, e.g. -p "-a --ion-eager testcase.js".')

    # Specify how to treat revisions that fail to compile.
    # (You might want to add these to kbew.knownBrokenRanges in known_broken_earliest_working.)
    parser.add_option("-l", "--compilationFailedLabel", dest="compilationFailedLabel",
                      help="Specify how to treat revisions that fail to compile. "
                           '(bad, good, or skip) Defaults to "%default"')

    parser.add_option("-T", "--useTreeherderBinaries",
                      dest="useTreeherderBinaries",
                      action="store_true",
                      help="Use treeherder binaries for quick bisection, assuming a fast "
                           'internet connection. Defaults to "%default"')
    parser.add_option("-N", "--nameOfTreeherderBranch",
                      dest="nameOfTreeherderBranch",
                      help='Name of the branch to download. Defaults to "%default"')

    (options, args) = parser.parse_args()
    if options.useTreeherderBinaries:
        print_("TBD: Bisection using downloaded shells is temporarily not supported.", flush=True)
        sys.exit(0)

    options.build_options = build_options.parse_shell_opts(options.build_options)
    options.skipRevs = " + ".join(kbew.known_broken_ranges(options.build_options))

    options.runtime_params = [x for x in options.parameters.split(" ") if x]

    # First check that the testcase is present.
    if "-e 42" not in options.parameters and not Path(options.runtime_params[-1]).expanduser().is_file():
        print_(flush=True)
        print_("List of parameters to be passed to the shell is: %s" % " ".join(options.runtime_params), flush=True)
        print_(flush=True)
        raise OSError("Testcase at %s is not present." % options.runtime_params[-1])

    assert options.compilationFailedLabel in ("bad", "good", "skip")

    extraFlags = []  # pylint: disable=invalid-name

    if options.useInterestingnessTests:
        if len(args) < 1:
            print_("args are: %s" % args, flush=True)
            parser.error("Not enough arguments.")
        for a in args:  # pylint: disable=invalid-name
            if a.startswith("--flags="):
                extraFlags = a[8:].split(" ")  # pylint: disable=invalid-name
        options.testAndLabel = externalTestAndLabel(options, args)
    elif len(args) >= 1:
        parser.error("Too many arguments.")
    else:
        options.testAndLabel = internalTestAndLabel(options)

    earliestKnownQuery = kbew.earliest_known_working_rev(  # pylint: disable=invalid-name
        options.build_options, options.runtime_params + extraFlags, options.skipRevs)

    earliestKnown = ""  # pylint: disable=invalid-name

    if not options.useTreeherderBinaries:
        # pylint: disable=invalid-name
        earliestKnown = hg_helpers.get_repo_hash_and_id(options.build_options.repo_dir, repo_rev=earliestKnownQuery)[0]

    if options.startRepo is None:
        if options.useTreeherderBinaries:
            options.startRepo = "default"
        else:
            options.startRepo = earliestKnown
    # elif not (options.useTreeherderBinaries or hg_helpers.isAncestor(options.build_options.repo_dir,
    #                                                              earliestKnown, options.startRepo)):
    #     raise Exception("startRepo is not a descendant of kbew.earliestKnownWorkingRev for this configuration")
    #
    # if not options.useTreeherderBinaries and not hg_helpers.isAncestor(options.build_options.repo_dir,
    #                                                                earliestKnown, options.endRepo):
    #     raise Exception("endRepo is not a descendant of kbew.earliestKnownWorkingRev for this configuration")

    if options.parameters == "-e 42":
        print_("Note: since no parameters were specified, "
               "we're just ensuring the shell does not crash on startup/shutdown.", flush=True)

    if options.nameOfTreeherderBranch != "mozilla-inbound" and not options.useTreeherderBinaries:
        raise Exception("Setting the name of branches only works for treeherder shell bisection.")

    return options


def findBlamedCset(options, repo_dir, testRev):  # pylint: disable=invalid-name,missing-docstring,too-complex
    # pylint: disable=too-many-locals,too-many-statements
    repo_dir = str(repo_dir)
    print_("%s | Bisecting on: %s" % (time.asctime(), repo_dir), flush=True)

    hgPrefix = ["hg", "-R", repo_dir]  # pylint: disable=invalid-name

    # Resolve names such as "tip", "default", or "52707" to stable hg hash ids, e.g. "9f2641871ce8".
    # pylint: disable=invalid-name
    realStartRepo = sRepo = hg_helpers.get_repo_hash_and_id(repo_dir, repo_rev=options.startRepo)[0]
    # pylint: disable=invalid-name
    realEndRepo = eRepo = hg_helpers.get_repo_hash_and_id(repo_dir, repo_rev=options.endRepo)[0]
    sps.vdump("Bisecting in the range " + sRepo + ":" + eRepo)

    # Refresh source directory (overwrite all local changes) to default tip if required.
    if options.resetRepoFirst:
        subprocess.run(hgPrefix + ["update", "-C", "default"], check=True)
        # Throws exit code 255 if purge extension is not enabled in .hgrc:
        subprocess.run(hgPrefix + ["purge", "--all"], check=True)

    # Reset bisect ranges and set skip ranges.
    subprocess.run(hgPrefix + ["bisect", "-r"],
                   check=True,
                   cwd=os.getcwdu() if sys.version_info.major == 2 else os.getcwd(),  # pylint: disable=no-member
                   timeout=99)
    if options.skipRevs:
        subprocess.run(hgPrefix + ["bisect", "--skip", options.skipRevs],
                       check=True,
                       cwd=os.getcwdu() if sys.version_info.major == 2 else os.getcwd(),  # pylint: disable=no-member
                       timeout=300)

    labels = {}
    # Specify `hg bisect` ranges.
    if options.testInitialRevs:
        currRev = eRepo  # If testInitialRevs mode is set, compile and test the latest rev first.
    else:
        labels[sRepo] = ("good", "assumed start rev is good")
        labels[eRepo] = ("bad", "assumed end rev is bad")
        subprocess.run(hgPrefix + ["bisect", "-U", "-g", sRepo], check=True)
        mid_bisect_output = subprocess.run(
            hgPrefix + ["bisect", "-U", "-b", eRepo],
            check=True,
            cwd=os.getcwdu() if sys.version_info.major == 2 else os.getcwd(),  # pylint: disable=no-member
            stdout=subprocess.PIPE,
            timeout=300).stdout.decode("utf-8", errors="replace")
        currRev = hg_helpers.get_cset_hash_from_bisect_msg(
            mid_bisect_output.split("\n"))

    iterNum = 1
    if options.testInitialRevs:
        iterNum -= 2

    skipCount = 0
    blamedRev = None

    while currRev is not None:
        startTime = time.time()
        label = testRev(currRev)
        labels[currRev] = label
        if label[0] == "skip":
            skipCount += 1
            # If we use "skip", we tell hg bisect to do a linear search to get around the skipping.
            # If the range is large, doing a bisect to find the start and endpoints of compilation
            # bustage would be faster. 20 total skips being roughly the time that the pair of
            # bisections would take.
            if skipCount > 20:
                print_("Skipped 20 times, stopping autobisectjs.", flush=True)
                break
        print_("%s (%s) " % (label[0], label[1]), end=" ", flush=True)

        if iterNum <= 0:
            print_("Finished testing the initial boundary revisions...", end=" ", flush=True)
        else:
            print_("Bisecting for the n-th round where n is %s and 2^n is %s ..." % (iterNum, 2**iterNum),
                   end=" ", flush=True)
        (blamedGoodOrBad, blamedRev, currRev, sRepo, eRepo) = \
            bisectLabel(hgPrefix, options, label[0], currRev, sRepo, eRepo)

        if options.testInitialRevs:
            options.testInitialRevs = False
            assert currRev is None
            currRev = sRepo  # If options.testInitialRevs is set, test earliest possible rev next.

        iterNum += 1
        endTime = time.time()
        oneRunTime = endTime - startTime
        print_("This iteration took %.3f seconds to run." % oneRunTime, flush=True)

    if blamedRev is not None:
        checkBlameParents(repo_dir, blamedRev, blamedGoodOrBad, labels, testRev, realStartRepo,
                          realEndRepo)

    sps.vdump("Resetting bisect")
    subprocess.run(hgPrefix + ["bisect", "-U", "-r"], check=True)

    sps.vdump("Resetting working directory")
    subprocess.run(hgPrefix + ["update", "-C", "-r", "default"],
                   check=True,
                   cwd=os.getcwdu() if sys.version_info.major == 2 else os.getcwd(),  # pylint: disable=no-member
                   timeout=999)
    hg_helpers.destroyPyc(repo_dir)

    print_(time.asctime(), flush=True)


def internalTestAndLabel(options):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc,too-complex
    """Use autobisectjs without interestingness tests to examine the revision of the js shell."""
    def inner(shellFilename, _hgHash):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc,too-many-return-statements
        # pylint: disable=invalid-name
        (stdoutStderr, exitCode) = inspect_shell.testBinary(shellFilename, options.runtime_params,
                                                            options.build_options.runWithVg)

        if (stdoutStderr.find(options.output) != -1) and (options.output != ""):
            return ("bad", "Specified-bad output")
        elif options.watchExitCode is not None and exitCode == options.watchExitCode:
            return ("bad", "Specified-bad exit code " + str(exitCode))
        elif options.watchExitCode is None and 129 <= exitCode <= 159:
            return ("bad", "High exit code " + str(exitCode))
        elif exitCode < 0:
            # On Unix-based systems, the exit code for signals is negative, so we check if
            # 128 + abs(exitCode) meets our specified signal exit code.
            if options.watchExitCode is not None and 128 - exitCode == options.watchExitCode:
                return ("bad", "Specified-bad exit code %s (after converting to signal)" % exitCode)
            elif (stdoutStderr.find(options.output) == -1) and (options.output != ""):
                return ("good", "Bad output, but not the specified one")
            elif options.watchExitCode is not None and 128 - exitCode != options.watchExitCode:
                return ("good", "Negative exit code, but not the specified one")
            return ("bad", "Negative exit code " + str(exitCode))
        elif exitCode == 0:
            return ("good", "Exit code 0")
        elif (exitCode == 1 or exitCode == 2) and (    # pylint: disable=too-many-boolean-expressions
                options.output != "") and (stdoutStderr.find("usage: js [") != -1 or
                                           stdoutStderr.find("Error: Short option followed by junk") != -1 or
                                           stdoutStderr.find("Error: Invalid long option:") != -1 or
                                           stdoutStderr.find("Error: Invalid short option:") != -1):
            return ("good", "Exit code 1 or 2 - js shell quits because it does not support a given CLI parameter")
        elif 3 <= exitCode <= 6:
            return ("good", "Acceptable exit code " + str(exitCode))
        elif options.watchExitCode is not None:
            return ("good", "Unknown exit code " + str(exitCode) + ", but not the specified one")
        return ("bad", "Unknown exit code " + str(exitCode))
    return inner


def externalTestAndLabel(options, interestingness):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Make use of interestingness scripts to decide whether the changeset is good or bad."""
    conditionScript = rel_or_abs_import(interestingness[0])  # pylint: disable=invalid-name
    conditionArgPrefix = interestingness[1:]  # pylint: disable=invalid-name

    def inner(shellFilename, hgHash):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc
        # pylint: disable=invalid-name
        conditionArgs = conditionArgPrefix + [str(shellFilename)] + options.runtime_params
        temp_dir = Path(tempfile.mkdtemp(prefix="abExtTestAndLabel-" + hgHash))
        temp_prefix = temp_dir / "t"
        if hasattr(conditionScript, "init"):
            # Since we're changing the js shell name, call init() again!
            conditionScript.init(conditionArgs)
        if conditionScript.interesting(conditionArgs, str(temp_prefix)):
            innerResult = ("bad", "interesting")  # pylint: disable=invalid-name
        else:
            innerResult = ("good", "not interesting")  # pylint: disable=invalid-name
        if temp_dir.is_dir():
            sps.rm_tree_incl_readonly(str(temp_dir))
        return innerResult
    return inner


# pylint: disable=invalid-name,missing-param-doc,missing-type-doc,too-many-arguments
def checkBlameParents(repo_dir, blamedRev, blamedGoodOrBad, labels, testRev, startRepo, endRepo):
    """If bisect blamed a merge, try to figure out why."""
    repo_dir = str(repo_dir)
    bisectLied = False
    missedCommonAncestor = False

    hg_parent_output = subprocess.run(
        ["hg", "-R", str(repo_dir)] + ["parent", "--template={node|short},", "-r", blamedRev],
        check=True,
        cwd=os.getcwdu() if sys.version_info.major == 2 else os.getcwd(),  # pylint: disable=no-member
        stdout=subprocess.PIPE,
        timeout=99).stdout.decode("utf-8", errors="replace")
    parents = hg_parent_output.split(",")[:-1]

    if len(parents) == 1:
        return

    for p in parents:
        # Ensure we actually tested the parent.
        if labels.get(p) is None:
            print_(flush=True)
            print_("Oops! We didn't test rev %s, a parent of the blamed revision! Let's do that now." % p, flush=True)
            if not hg_helpers.isAncestor(repo_dir, startRepo, p) and \
                    not hg_helpers.isAncestor(repo_dir, endRepo, p):
                print_("We did not test rev %s because it is not a descendant of either %s or %s." % (
                    p, startRepo, endRepo), flush=True)
                # Note this in case we later decide the bisect result is wrong.
                missedCommonAncestor = True
            label = testRev(p)
            labels[p] = label
            print_("%s (%s) " % (label[0], label[1]), flush=True)
            print_("As expected, the parent's label is the opposite of the blamed rev's label.", flush=True)

        # Check that the parent's label is the opposite of the blamed merge's label.
        if labels[p][0] == "skip":
            print_('Parent rev %s was marked as "skip", so the regression window includes it.' % (p,), flush=True)
        elif labels[p][0] == blamedGoodOrBad:
            print_("Bisect lied to us! Parent rev %s was also %s!" % (p, blamedGoodOrBad), flush=True)
            bisectLied = True
        else:
            assert labels[p][0] == {"good": "bad", "bad": "good"}[blamedGoodOrBad]

    # Explain why bisect blamed the merge.
    if bisectLied:
        if missedCommonAncestor:
            ca = hg_helpers.findCommonAncestor(repo_dir, parents[0], parents[1])
            print_(flush=True)
            print_("Bisect blamed the merge because our initial range did not include one", flush=True)
            print_("of the parents.", flush=True)
            print_("The common ancestor of %s and %s is %s." % (parents[0], parents[1], ca), flush=True)
            label = testRev(ca)
            print_("%s (%s) " % (label[0], label[1]), flush=True)
            print_("Consider re-running autobisectjs with -s %s -e %s" % (ca, blamedRev), flush=True)
            print_("in a configuration where earliestWorking is before the common ancestor.", flush=True)
        else:
            print_(flush=True)
            print_("Most likely, bisect's result was unhelpful because one of the", flush=True)
            print_('tested revisions was marked as "good" or "bad" for the wrong reason.', flush=True)
            print_("I don't know which revision was incorrectly marked. Sorry.", flush=True)
    else:
        print_(flush=True)
        print_("The bug was introduced by a merge (it was not present on either parent).", flush=True)
        print_("I don't know which patches from each side of the merge contributed to the bug. Sorry.", flush=True)


def sanitizeCsetMsg(msg, repo):  # pylint: disable=missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Sanitize changeset messages, removing email addresses."""
    msgList = msg.split("\n")
    sanitizedMsgList = []
    for line in msgList:
        if line.find("<") != -1 and line.find("@") != -1 and line.find(">") != -1:
            line = " ".join(line.split(" ")[:-1])
        elif line.startswith("changeset:") and "mozilla-central" in str(repo):
            line = "changeset:   https://hg.mozilla.org/mozilla-central/rev/" + line.split(":")[-1]
        sanitizedMsgList.append(line)
    return "\n".join(sanitizedMsgList)


def bisectLabel(hgPrefix, options, hgLabel, currRev, startRepo, endRepo):  # pylint: disable=invalid-name
    # pylint: disable=missing-param-doc,missing-raises-doc,missing-return-doc,missing-return-type-doc,missing-type-doc
    # pylint: disable=too-many-arguments
    """Tell hg what we learned about the revision."""
    assert hgLabel in ("good", "bad", "skip")
    outputResult = subprocess.run(
        hgPrefix + ["bisect", "-U", "--" + hgLabel, currRev],
        check=True,
        cwd=os.getcwdu() if sys.version_info.major == 2 else os.getcwd(),  # pylint: disable=no-member
        stdout=subprocess.PIPE,
        timeout=999).stdout.decode("utf-8", errors="replace")
    outputLines = outputResult.split("\n")

    if options.build_options:
        repo_dir = options.build_options.repo_dir

    if re.compile("Due to skipped revisions, the first (good|bad) revision could be any of:").match(outputLines[0]):
        print_(flush=True)
        print_(sanitizeCsetMsg(outputResult, repo_dir), flush=True)
        print_(flush=True)
        return None, None, None, startRepo, endRepo

    r = re.compile("The first (good|bad) revision is:")
    m = r.match(outputLines[0])
    if m:
        print_(flush=True)
        print_(flush=True)
        print_("autobisectjs shows this is probably related to the following changeset:", flush=True)
        print_(flush=True)
        print_(sanitizeCsetMsg(outputResult, repo_dir), flush=True)
        print_(flush=True)
        blamedGoodOrBad = m.group(1)
        blamedRev = hg_helpers.get_cset_hash_from_bisect_msg(outputLines[1])
        return blamedGoodOrBad, blamedRev, None, startRepo, endRepo

    if options.testInitialRevs:
        return None, None, None, startRepo, endRepo

    # e.g. "Testing changeset 52121:573c5fa45cc4 (440 changesets remaining, ~8 tests)"
    sps.vdump(outputLines[0])

    currRev = hg_helpers.get_cset_hash_from_bisect_msg(outputLines[0])
    if currRev is None:
        print_("Resetting to default revision...", flush=True)
        subprocess.run(hgPrefix + ["update", "-C", "default"], check=True)
        hg_helpers.destroyPyc(repo_dir)
        raise Exception("hg did not suggest a changeset to test!")

    # Update the startRepo/endRepo values.
    start = startRepo
    end = endRepo
    if hgLabel == "bad":
        end = currRev
    elif hgLabel == "good":
        start = currRev
    elif hgLabel == "skip":
        pass

    return None, None, currRev, start, end


def rm_old_local_cached_dirs(cache_dir):
    """Remove old local cached directories, which were created four weeks ago.

    Args:
        cache_dir (Path): Full path to the cache directory
    """
    assert isinstance(cache_dir, Path)
    cache_dir = cache_dir.expanduser()

    # This is in autobisectjs because it has a lock so we do not race while removing directories
    # Adapted from http://stackoverflow.com/a/11337407
    SECONDS_IN_A_DAY = 24 * 60 * 60
    s3CacheObj = s3cache.S3Cache(compile_shell.S3_SHELL_CACHE_DIRNAME)
    if s3CacheObj.connect():
        NUMBER_OF_DAYS = 1  # EC2 VMs generally have less disk space for local shell caches
    else:
        NUMBER_OF_DAYS = 28

    names = [cache_dir / x for x in cache_dir.iterdir()]

    for name in names:
        if name.is_dir():
            timediff = time.mktime(time.gmtime()) - Path.stat(name).st_atime
            if timediff > SECONDS_IN_A_DAY * NUMBER_OF_DAYS:
                shutil.rmtree(str(name))


def main():
    """Prevent running two instances of autobisectjs concurrently - we don't want to confuse hg."""
    options = parseOpts()

    if options.build_options:
        repo_dir = options.build_options.repo_dir

    with LockDir(sm_compile_helpers.get_lock_dir_path(Path.home(), options.nameOfTreeherderBranch, tbox_id="Tbox")
                 if options.useTreeherderBinaries else sm_compile_helpers.get_lock_dir_path(Path.home(), repo_dir)):
        if options.useTreeherderBinaries:
            print_("TBD: We need to switch to the autobisect repository.", flush=True)
            sys.exit(0)
        else:  # Bisect using local builds
            findBlamedCset(options, repo_dir, compile_shell.makeTestRev(options))

        # Last thing we do while we have a lock.
        # Note that this only clears old *local* cached directories, not remote ones.
        rm_old_local_cached_dirs(sm_compile_helpers.ensure_cache_dir(Path.home()))

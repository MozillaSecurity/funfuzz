# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""autobisectjs, for bisecting changeset regression windows. Supports Mercurial repositories and SpiderMonkey only.
"""

from __future__ import absolute_import, print_function

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from optparse import OptionParser  # pylint: disable=deprecated-module

from backports.print_function import print_
from lithium.interestingness.utils import rel_or_abs_import

from . import known_broken_earliest_working as kbew
from ..js import build_options
from ..js import compare_jit
from ..js import compile_shell
from ..js import inspect_shell
from ..js import js_interesting
from ..util import hg_helpers
from ..util.lock_dir import LockDir
from ..util import s3cache
from ..util import subprocesses as sps


def parseOpts():  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    # pylint: disable=too-many-branches,too-complex,too-many-statements
    usage = 'Usage: %prog [options]'
    parser = OptionParser(usage)
    # http://docs.python.org/library/optparse.html#optparse.OptionParser.disable_interspersed_args
    parser.disable_interspersed_args()

    parser.set_defaults(
        resetRepoFirst=False,
        startRepo=None,
        endRepo='default',
        testInitialRevs=True,
        output='',
        watchExitCode=None,
        useInterestingnessTests=False,
        parameters='-e 42',  # http://en.wikipedia.org/wiki/The_Hitchhiker%27s_Guide_to_the_Galaxy
        compilationFailedLabel='skip',
        build_options="",
        useTreeherderBinaries=False,
        nameOfTreeherderBranch='mozilla-inbound',
    )

    # Specify how the shell will be built.
    parser.add_option('-b', '--build',
                      dest='build_options',
                      help='Specify js shell build options, e.g. -b "--enable-debug --32"'
                           "(python -m funfuzz.js.build_options --help)")

    parser.add_option('--resetToTipFirst', dest='resetRepoFirst',
                      action='store_true',
                      help="First reset to default tip overwriting all local changes. "
                           "Equivalent to first executing `hg update -C default`. Defaults to '%default'.")

    # Specify the revisions between which to bisect.
    parser.add_option('-s', '--startRev', dest='startRepo',
                      help="Earliest changeset/build numeric ID to consider (usually a 'good' cset). "
                           "Defaults to the earliest revision known to work at all/available.")
    parser.add_option('-e', '--endRev', dest='endRepo',
                      help="Latest changeset/build numeric ID to consider (usually a 'bad' cset). "
                           "Defaults to the head of the main branch, 'default', or latest available build.")
    parser.add_option('-k', '--skipInitialRevs', dest='testInitialRevs',
                      action='store_false',
                      help="Skip testing the -s and -e revisions and automatically trust them as -g and -b.")

    # Specify the type of failure to look for.
    # (Optional -- by default, internalTestAndLabel will look for exit codes that indicate a crash or assert.)
    parser.add_option('-o', '--output', dest='output',
                      help="Stdout or stderr output to be observed. Defaults to '%default'. "
                           "For assertions, set to 'ssertion fail'")
    parser.add_option('-w', '--watchExitCode', dest='watchExitCode',
                      type='int',
                      help="Look out for a specific exit code. Only this exit code will be considered 'bad'.")
    parser.add_option('-i', '--useInterestingnessTests',
                      dest='useInterestingnessTests',
                      action="store_true",
                      help="Interpret the final arguments as an interestingness test.")

    # Specify parameters for the js shell.
    parser.add_option('-p', '--parameters', dest='parameters',
                      help='Specify parameters for the js shell, e.g. -p "-a --ion-eager testcase.js".')

    # Specify how to treat revisions that fail to compile.
    # (You might want to add these to kbew.knownBrokenRanges in known_broken_earliest_working.)
    parser.add_option('-l', '--compilationFailedLabel', dest='compilationFailedLabel',
                      help="Specify how to treat revisions that fail to compile. "
                           "(bad, good, or skip) Defaults to '%default'")

    parser.add_option('-T', '--useTreeherderBinaries',
                      dest='useTreeherderBinaries',
                      action="store_true",
                      help="Use treeherder binaries for quick bisection, assuming a fast "
                           "internet connection. Defaults to '%default'")
    parser.add_option('-N', '--nameOfTreeherderBranch',
                      dest='nameOfTreeherderBranch',
                      help='Name of the branch to download. Defaults to "%default"')

    (options, args) = parser.parse_args()
    if options.useTreeherderBinaries:
        print_("TBD: Bisection using downloaded shells is temporarily not supported.", flush=True)
        sys.exit(0)

    options.build_options = build_options.parseShellOptions(options.build_options)
    options.skipRevs = ' + '.join(kbew.known_broken_ranges(options.build_options))

    options.paramList = [sps.normExpUserPath(x) for x in options.parameters.split(' ') if x]
    # First check that the testcase is present.
    if '-e 42' not in options.parameters and not os.path.isfile(options.paramList[-1]):
        print_(flush=True)
        print_("List of parameters to be passed to the shell is: %s" % " ".join(options.paramList), flush=True)
        print_(flush=True)
        raise Exception('Testcase at ' + options.paramList[-1] + ' is not present.')

    assert options.compilationFailedLabel in ('bad', 'good', 'skip')

    extraFlags = []  # pylint: disable=invalid-name

    if options.useInterestingnessTests:
        if len(args) < 1:
            print_("args are: %s" % args, flush=True)
            parser.error('Not enough arguments.')
        for a in args:  # pylint: disable=invalid-name
            if a.startswith("--flags="):
                extraFlags = a[8:].split(' ')  # pylint: disable=invalid-name
        options.testAndLabel = externalTestAndLabel(options, args)
    elif len(args) >= 1:
        parser.error('Too many arguments.')
    else:
        options.testAndLabel = internalTestAndLabel(options)

    earliestKnownQuery = kbew.earliest_known_working_rev(  # pylint: disable=invalid-name
        options.build_options, options.paramList + extraFlags, options.skipRevs)

    earliestKnown = ''  # pylint: disable=invalid-name

    if not options.useTreeherderBinaries:
        # pylint: disable=invalid-name
        earliestKnown = hg_helpers.getRepoHashAndId(options.build_options.repoDir, repoRev=earliestKnownQuery)[0]

    if options.startRepo is None:
        if options.useTreeherderBinaries:
            options.startRepo = 'default'
        else:
            options.startRepo = earliestKnown
    # elif not (options.useTreeherderBinaries or hg_helpers.isAncestor(options.build_options.repoDir,
    #                                                              earliestKnown, options.startRepo)):
    #     raise Exception('startRepo is not a descendant of kbew.earliestKnownWorkingRev for this configuration')
    #
    # if not options.useTreeherderBinaries and not hg_helpers.isAncestor(options.build_options.repoDir,
    #                                                                earliestKnown, options.endRepo):
    #     raise Exception('endRepo is not a descendant of kbew.earliestKnownWorkingRev for this configuration')

    if options.parameters == '-e 42':
        print_("Note: since no parameters were specified, "
               "we're just ensuring the shell does not crash on startup/shutdown.", flush=True)

    if options.nameOfTreeherderBranch != 'mozilla-inbound' and not options.useTreeherderBinaries:
        raise Exception('Setting the name of branches only works for treeherder shell bisection.')

    return options


def findBlamedCset(options, repoDir, testRev):  # pylint: disable=invalid-name,missing-docstring,too-complex
    # pylint: disable=too-many-locals,too-many-statements
    print_("%s | Bisecting on: %s" % (time.asctime(), repoDir), flush=True)

    hgPrefix = ['hg', '-R', repoDir]  # pylint: disable=invalid-name

    # Resolve names such as "tip", "default", or "52707" to stable hg hash ids, e.g. "9f2641871ce8".
    # pylint: disable=invalid-name
    realStartRepo = sRepo = hg_helpers.getRepoHashAndId(repoDir, repoRev=options.startRepo)[0]
    # pylint: disable=invalid-name
    realEndRepo = eRepo = hg_helpers.getRepoHashAndId(repoDir, repoRev=options.endRepo)[0]
    sps.vdump("Bisecting in the range " + sRepo + ":" + eRepo)

    # Refresh source directory (overwrite all local changes) to default tip if required.
    if options.resetRepoFirst:
        subprocess.check_call(hgPrefix + ['update', '-C', 'default'])
        # Throws exit code 255 if purge extension is not enabled in .hgrc:
        subprocess.check_call(hgPrefix + ['purge', '--all'])

    # Reset bisect ranges and set skip ranges.
    sps.captureStdout(hgPrefix + ['bisect', '-r'])
    if options.skipRevs:
        sps.captureStdout(hgPrefix + ['bisect', '--skip', options.skipRevs])

    labels = {}
    # Specify `hg bisect` ranges.
    if options.testInitialRevs:
        currRev = eRepo  # If testInitialRevs mode is set, compile and test the latest rev first.
    else:
        labels[sRepo] = ('good', 'assumed start rev is good')
        labels[eRepo] = ('bad', 'assumed end rev is bad')
        subprocess.check_call(hgPrefix + ['bisect', '-U', '-g', sRepo])
        currRev = hg_helpers.get_cset_hash_from_bisect_msg(
            sps.captureStdout(hgPrefix + ['bisect', '-U', '-b', eRepo])[0].split('\n')[0])

    iterNum = 1
    if options.testInitialRevs:
        iterNum -= 2

    skipCount = 0
    blamedRev = None

    while currRev is not None:
        startTime = time.time()
        label = testRev(currRev)
        labels[currRev] = label
        if label[0] == 'skip':
            skipCount += 1
            # If we use "skip", we tell hg bisect to do a linear search to get around the skipping.
            # If the range is large, doing a bisect to find the start and endpoints of compilation
            # bustage would be faster. 20 total skips being roughly the time that the pair of
            # bisections would take.
            if skipCount > 20:
                print_("Skipped 20 times, stopping autoBisect.", flush=True)
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
        checkBlameParents(repoDir, blamedRev, blamedGoodOrBad, labels, testRev, realStartRepo,
                          realEndRepo)

    sps.vdump("Resetting bisect")
    subprocess.check_call(hgPrefix + ['bisect', '-U', '-r'])

    sps.vdump("Resetting working directory")
    sps.captureStdout(hgPrefix + ['update', '-C', '-r', 'default'], ignoreStderr=True)
    hg_helpers.destroyPyc(repoDir)

    print_(time.asctime(), flush=True)


def internalTestAndLabel(options):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc,too-complex
    """Use autoBisectJs without interestingness tests to examine the revision of the js shell."""
    def inner(shellFilename, _hgHash):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc,too-many-return-statements
        # pylint: disable=invalid-name
        (stdoutStderr, exitCode) = inspect_shell.testBinary(shellFilename, options.paramList,
                                                            options.build_options.runWithVg)

        if (stdoutStderr.find(options.output) != -1) and (options.output != ''):
            return ('bad', 'Specified-bad output')
        elif options.watchExitCode is not None and exitCode == options.watchExitCode:
            return ('bad', 'Specified-bad exit code ' + str(exitCode))
        elif options.watchExitCode is None and 129 <= exitCode <= 159:
            return ('bad', 'High exit code ' + str(exitCode))
        elif exitCode < 0:
            # On Unix-based systems, the exit code for signals is negative, so we check if
            # 128 + abs(exitCode) meets our specified signal exit code.
            if options.watchExitCode is not None and 128 - exitCode == options.watchExitCode:
                return ("bad", "Specified-bad exit code %s (after converting to signal)" % exitCode)
            elif (stdoutStderr.find(options.output) == -1) and (options.output != ''):
                return ('good', 'Bad output, but not the specified one')
            elif options.watchExitCode is not None and 128 - exitCode != options.watchExitCode:
                return ('good', 'Negative exit code, but not the specified one')
            return ('bad', 'Negative exit code ' + str(exitCode))
        elif exitCode == 0:
            return ('good', 'Exit code 0')
        elif (exitCode == 1 or exitCode == 2) and (    # pylint: disable=too-many-boolean-expressions
                options.output != '') and (stdoutStderr.find('usage: js [') != -1 or
                                           stdoutStderr.find('Error: Short option followed by junk') != -1 or
                                           stdoutStderr.find('Error: Invalid long option:') != -1 or
                                           stdoutStderr.find('Error: Invalid short option:') != -1):
            return ("good", "Exit code 1 or 2 - js shell quits because it does not support a given CLI parameter")
        elif 3 <= exitCode <= 6:
            return ('good', 'Acceptable exit code ' + str(exitCode))
        elif options.watchExitCode is not None:
            return ('good', 'Unknown exit code ' + str(exitCode) + ', but not the specified one')
        return ('bad', 'Unknown exit code ' + str(exitCode))
    return inner


def externalTestAndLabel(options, interestingness):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Make use of interestingness scripts to decide whether the changeset is good or bad."""
    interestingness_name = interestingness[0]
    conditionScript = rel_or_abs_import(interestingness_name)  # pylint: disable=invalid-name
    conditionArgPrefix = interestingness[1:]  # pylint: disable=invalid-name

    def inner(shellFilename, hgHash):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc
        conditionArgs = conditionArgPrefix + [shellFilename] + options.paramList  # pylint: disable=invalid-name
        tempDir = tempfile.mkdtemp(prefix="abExtTestAndLabel-" + hgHash)  # pylint: disable=invalid-name
        tempPrefix = os.path.join(tempDir, 't')  # pylint: disable=invalid-name

        assert "js_interesting" in interestingness_name or "compare_jit" in interestingness_name
        if "js_interesting" in interestingness_name:
            opts = js_interesting.parseOptions(conditionArgs)
        elif "compare_jit" in interestingness_name:
            opts = compare_jit.parseOptions(conditionArgs)
        else:
            raise ValueError("Invalid condition script specified: %s" % interestingness_name)

        if conditionScript.interesting(opts, tempPrefix):
            innerResult = ('bad', 'interesting')  # pylint: disable=invalid-name
        else:
            innerResult = ('good', 'not interesting')  # pylint: disable=invalid-name
        if os.path.isdir(tempDir):
            sps.rmTreeIncludingReadOnly(tempDir)
        return innerResult
    return inner


# pylint: disable=invalid-name,missing-param-doc,missing-type-doc,too-many-arguments
def checkBlameParents(repoDir, blamedRev, blamedGoodOrBad, labels, testRev, startRepo, endRepo):
    """If bisect blamed a merge, try to figure out why."""
    bisectLied = False
    missedCommonAncestor = False

    parents = sps.captureStdout(["hg", "-R", repoDir] + ["parent", '--template={node|short},',
                                                         "-r", blamedRev])[0].split(",")[:-1]

    if len(parents) == 1:
        return

    for p in parents:
        # Ensure we actually tested the parent.
        if labels.get(p) is None:
            print_(flush=True)
            print_("Oops! We didn't test rev %s, a parent of the blamed revision! Let's do that now." % p, flush=True)
            if not hg_helpers.isAncestor(repoDir, startRepo, p) and \
                    not hg_helpers.isAncestor(repoDir, endRepo, p):
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
            print_("Parent rev %s was marked as 'skip', so the regression window includes it." % (p,), flush=True)
        elif labels[p][0] == blamedGoodOrBad:
            print_("Bisect lied to us! Parent rev %s was also %s!" % (p, blamedGoodOrBad), flush=True)
            bisectLied = True
        else:
            assert labels[p][0] == {'good': 'bad', 'bad': 'good'}[blamedGoodOrBad]

    # Explain why bisect blamed the merge.
    if bisectLied:
        if missedCommonAncestor:
            ca = hg_helpers.findCommonAncestor(repoDir, parents[0], parents[1])
            print_(flush=True)
            print_("Bisect blamed the merge because our initial range did not include one", flush=True)
            print_("of the parents.", flush=True)
            print_("The common ancestor of %s and %s is %s." % (parents[0], parents[1], ca), flush=True)
            label = testRev(ca)
            print_("%s (%s) " % (label[0], label[1]), flush=True)
            print_("Consider re-running autoBisect with -s %s -e %s" % (ca, blamedRev), flush=True)
            print_("in a configuration where earliestWorking is before the common ancestor.", flush=True)
        else:
            print_(flush=True)
            print_("Most likely, bisect's result was unhelpful because one of the", flush=True)
            print_("tested revisions was marked as 'good' or 'bad' for the wrong reason.", flush=True)
            print_("I don't know which revision was incorrectly marked. Sorry.", flush=True)
    else:
        print_(flush=True)
        print_("The bug was introduced by a merge (it was not present on either parent).", flush=True)
        print_("I don't know which patches from each side of the merge contributed to the bug. Sorry.", flush=True)


def sanitizeCsetMsg(msg, repo):  # pylint: disable=missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Sanitize changeset messages, removing email addresses."""
    msgList = msg.split('\n')
    sanitizedMsgList = []
    for line in msgList:
        if line.find('<') != -1 and line.find('@') != -1 and line.find('>') != -1:
            line = ' '.join(line.split(' ')[:-1])
        elif line.startswith('changeset:') and 'mozilla-central' in repo:
            line = 'changeset:   https://hg.mozilla.org/mozilla-central/rev/' + line.split(':')[-1]
        sanitizedMsgList.append(line)
    return '\n'.join(sanitizedMsgList)


def bisectLabel(hgPrefix, options, hgLabel, currRev, startRepo, endRepo):  # pylint: disable=invalid-name
    # pylint: disable=missing-param-doc,missing-raises-doc,missing-return-doc,missing-return-type-doc,missing-type-doc
    # pylint: disable=too-many-arguments
    """Tell hg what we learned about the revision."""
    assert hgLabel in ("good", "bad", "skip")
    outputResult = sps.captureStdout(hgPrefix + ['bisect', '-U', '--' + hgLabel, currRev])[0]
    outputLines = outputResult.split("\n")

    if options.build_options:
        repoDir = options.build_options.repoDir

    if re.compile("Due to skipped revisions, the first (good|bad) revision could be any of:").match(outputLines[0]):
        print_(flush=True)
        print_(sanitizeCsetMsg(outputResult, repoDir), flush=True)
        print_(flush=True)
        return None, None, None, startRepo, endRepo

    r = re.compile("The first (good|bad) revision is:")
    m = r.match(outputLines[0])
    if m:
        print_(flush=True)
        print_(flush=True)
        print_("autoBisect shows this is probably related to the following changeset:", flush=True)
        print_(flush=True)
        print_(sanitizeCsetMsg(outputResult, repoDir), flush=True)
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
        subprocess.check_call(hgPrefix + ['update', '-C', 'default'])
        hg_helpers.destroyPyc(repoDir)
        raise Exception("hg did not suggest a changeset to test!")

    # Update the startRepo/endRepo values.
    start = startRepo
    end = endRepo
    if hgLabel == 'bad':
        end = currRev
    elif hgLabel == 'good':
        start = currRev
    elif hgLabel == 'skip':
        pass

    return None, None, currRev, start, end


def rmOldLocalCachedDirs(cacheDir):  # pylint: disable=missing-param-doc,missing-type-doc
    """Remove old local cached directories, which were created four weeks ago."""
    # This is in autoBisect because it has a lock so we do not race while removing directories
    # Adapted from http://stackoverflow.com/a/11337407
    SECONDS_IN_A_DAY = 24 * 60 * 60
    s3CacheObj = s3cache.S3Cache(compile_shell.S3_SHELL_CACHE_DIRNAME)
    if s3CacheObj.connect():
        NUMBER_OF_DAYS = 1  # EC2 VMs generally have less disk space for local shell caches
    else:
        NUMBER_OF_DAYS = 28

    cacheDir = sps.normExpUserPath(cacheDir)
    names = [os.path.join(cacheDir, fname) for fname in os.listdir(cacheDir)]

    for name in names:
        if os.path.isdir(name):
            timediff = time.mktime(time.gmtime()) - os.stat(name).st_atime
            if timediff > SECONDS_IN_A_DAY * NUMBER_OF_DAYS:
                shutil.rmtree(name)


def main():
    """Prevent running two instances of autoBisectJs concurrently - we don't want to confuse hg."""
    options = parseOpts()

    if options.build_options:
        repoDir = options.build_options.repoDir

    with LockDir(compile_shell.getLockDirPath(options.nameOfTreeherderBranch, tboxIdentifier='Tbox')
                 if options.useTreeherderBinaries else compile_shell.getLockDirPath(repoDir)):
        if options.useTreeherderBinaries:
            print_("TBD: We need to switch to the autobisect repository.", flush=True)
            sys.exit(0)
        else:  # Bisect using local builds
            findBlamedCset(options, repoDir, compile_shell.makeTestRev(options))

        # Last thing we do while we have a lock.
        # Note that this only clears old *local* cached directories, not remote ones.
        rmOldLocalCachedDirs(compile_shell.ensureCacheDir())

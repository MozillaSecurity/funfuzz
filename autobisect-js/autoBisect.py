#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import math
import os
import platform
import re
import shutil
import subprocess
import sys
import time

from optparse import OptionParser
from tempfile import mkdtemp

from knownBrokenEarliestWorking import knownBrokenRanges, knownBrokenRangesBrowser, earliestKnownWorkingRev, earliestKnownWorkingRevForBrowser

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'interestingness'))
sys.path.append(path1)
import ximport
path2 = os.path.abspath(os.path.join(path0, os.pardir, 'js'))
sys.path.append(path2)
from compileShell import CompiledShell, makeTestRev, ensureCacheDir
from inspectShell import testBinary
path3 = os.path.abspath(os.path.join(path0, os.pardir, 'dom', 'automation'))
sys.path.append(path3)
import buildBrowser
path4 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path4)
from fileManipulation import firstLine
import buildOptions
from downloadBuild import defaultBuildType, downloadBuild, getBuildList
from hgCmds import findCommonAncestor, getCsetHashFromBisectMsg, getRepoHashAndId, isAncestor, destroyPyc
from subprocesses import captureStdout, dateStr, isVM, isWin, normExpUserPath, Unbuffered, vdump


def sanityChecks():
    # autoBisect uses temporary directory python APIs. On WinXP, these are located at
    # c:\docume~1\mozilla\locals~1\temp\ and the ~ in the shortened folders break pymake.
    # This can be fixed by moving compilations to autobisect-cache, but we lose the benefit of
    # compiling in a temporary directory. Not worth it, for an OS that is on its way out.
    assert platform.uname()[2] != 'XP'
    # Disable autoBisect when running in a VM, even Linux. This has the possibility of interacting
    # with the repositories in the trees directory as they can update to a different changeset
    # within the VM. It should work when running manually though.
    assert isVM()[1] == False

def parseOpts():
    usage = 'Usage: %prog [options]'
    parser = OptionParser(usage)
    # http://docs.python.org/library/optparse.html#optparse.OptionParser.disable_interspersed_args
    parser.disable_interspersed_args()

    parser.set_defaults(
        resetRepoFirst = False,
        startRepo = None,
        endRepo = 'default',
        testInitialRevs = True,
        output = '',
        watchExitCode = None,
        useInterestingnessTests = False,
        parameters = '-e 42',  # http://en.wikipedia.org/wiki/The_Hitchhiker%27s_Guide_to_the_Galaxy
        compilationFailedLabel = 'skip',
        buildOptions = "",
        useTinderboxBinaries = False,
        nameOfTinderboxBranch = 'mozilla-inbound',
    )

    # Specify how the shell will be built.
    # See buildOptions.py for details.
    parser.add_option('-b', '--build',
                      dest='buildOptions',
                      help='Specify js shell build options, e.g. -b "-c opt --arch=32" (python buildOptions.py --help)')
    parser.add_option('-B', '--browser',
                      dest='browserOptions',
                      help='Specify browser build options, e.g. -b "-c mozconfig"')

    parser.add_option('--resetToTipFirst', dest='resetRepoFirst',
                      action='store_true',
                      help='First reset to default tip overwriting all local changes. ' + \
                           'Equivalent to first executing `hg update -C default`. ' + \
                           'Defaults to "%default".')

    # Specify the revisions between which to bisect.
    parser.add_option('-s', '--startRev', dest='startRepo',
                      help='Earliest changeset/build numeric ID to consider (usually a "good" cset). ' + \
                           'Defaults to the earliest revision known to work at all/available.')
    parser.add_option('-e', '--endRev', dest='endRepo',
                      help='Latest changeset/build numeric ID to consider (usually a "bad" cset). ' + \
                           'Defaults to the head of the main branch, "default", or latest available build.')
    parser.add_option('-k', '--skipInitialRevs', dest='testInitialRevs',
                      action='store_false',
                      help='Skip testing the -s and -e revisions and automatically trust them ' + \
                           'as -g and -b.')

    # Specify the type of failure to look for.
    # (Optional -- by default, internalTestAndLabel will look for exit codes that indicate a crash or assert.)
    parser.add_option('-o', '--output', dest='output',
                      help='Stdout or stderr output to be observed. Defaults to "%default". ' + \
                           'For assertions, set to "ssertion fail"')
    parser.add_option('-w', '--watchExitCode', dest='watchExitCode',
                      type='int',
                      help='Look out for a specific exit code. Only this exit code will be ' + \
                           'considered "bad".')
    parser.add_option('-i', '--useInterestingnessTests',
                      dest='useInterestingnessTests',
                      action="store_true",
                      help="Interpret the final arguments as an interestingness test.")

    # Specify parameters for the js shell.
    parser.add_option('-p', '--parameters', dest='parameters',
                      help='Specify parameters for the js shell, e.g. -p "-a --ion-eager testcase.js".')

    # Specify how to treat revisions that fail to compile.
    # (You might want to add these to knownBrokenRanges in knownBrokenEarliestWorking.py.)
    parser.add_option('-l', '--compilationFailedLabel', dest='compilationFailedLabel',
                      help='Specify how to treat revisions that fail to compile. ' + \
                            '(bad, good, or skip) Defaults to "%default"')

    parser.add_option('-T', '--useTinderboxBinaries',
                      dest='useTinderboxBinaries',
                      action="store_true",
                      help='Use tinderbox binaries for quick bisection, assuming a fast ' + \
                           'internet connection. Defaults to "%default"')
    parser.add_option('-N', '--nameOfTinderboxBranch',
                      dest='nameOfTinderboxBranch',
                      help='Name of the branch to download. Defaults to "%default"')

    (options, args) = parser.parse_args()
    if options.browserOptions:
        assert not options.buildOptions
        options.browserOptions = buildBrowser.parseOptions(options.browserOptions.split())
        options.skipRevs = ' + '.join(knownBrokenRangesBrowser(options.browserOptions))
    else:
        options.buildOptions = buildOptions.parseShellOptions(options.buildOptions)
        options.skipRevs = ' + '.join(knownBrokenRanges(options.buildOptions))

    options.paramList = [normExpUserPath(x) for x in options.parameters.split(' ') if x]
    # First check that the testcase is present.
    if options.parameters is not '-e 42' and not os.path.isfile(options.paramList[-1]):
        print '\nList of parameters to be passed to the shell is: ' + ' '.join(options.paramList)
        print
        raise Exception('Testcase at ' + options.paramList[-1] + ' is not present.')

    assert options.compilationFailedLabel in ('bad', 'good', 'skip')

    extraFlags = []

    if options.useInterestingnessTests:
        if len(args) < 1:
            print 'args are: ' + args
            parser.error('Not enough arguments.')
        if not options.browserOptions:
            for a in args:
                if a.startswith("--flags="):
                    extraFlags = a[8:].split(' ')
        options.testAndLabel = externalTestAndLabel(options, args)
    else:
        assert not options.browserOptions # autoBisect doesn't have a built-in way to run the browser
        if len(args) >= 1:
            parser.error('Too many arguments.')
        options.testAndLabel = internalTestAndLabel(options)

    if options.startRepo is None:
        if options.browserOptions:
            options.startRepo = earliestKnownWorkingRevForBrowser(options.browserOptions)
        else:
            options.startRepo = 'default' if options.useTinderboxBinaries is True else \
                earliestKnownWorkingRev(options.buildOptions, options.paramList + extraFlags, options.skipRevs)

    if options.parameters == '-e 42':
        print "Note: since no parameters were specified, we're just ensuring the shell does not crash on startup/shutdown."
        if options.useTinderboxBinaries:
            print '\nWARNING: Not downloading binaries, because no parameters were set via "-p".'
            print 'Quitting...\n'
            sys.exit(0)

    if options.nameOfTinderboxBranch != 'mozilla-inbound' and not options.useTinderboxBinaries:
        raise Exception('Setting the name of branches only works for tinderbox shell bisection.')

    return options

def findBlamedCset(options, repoDir, testRev):
    print dateStr()

    hgPrefix = ['hg', '-R', repoDir]

    # Resolve names such as "tip", "default", or "52707" to stable hg hash ids, e.g. "9f2641871ce8".
    realStartRepo = sRepo = getRepoHashAndId(repoDir, repoRev=options.startRepo)[0]
    realEndRepo = eRepo = getRepoHashAndId(repoDir, repoRev=options.endRepo)[0]
    vdump("Bisecting in the range " + sRepo + ":" + eRepo)

    # Refresh source directory (overwrite all local changes) to default tip if required.
    if options.resetRepoFirst:
        subprocess.check_call(hgPrefix + ['update', '-C', 'default'])
         # Throws exit code 255 if purge extension is not enabled in .hgrc:
        subprocess.check_call(hgPrefix + ['purge', '--all'])

    # Reset bisect ranges and set skip ranges.
    captureStdout(hgPrefix + ['bisect', '-r'])
    if options.skipRevs:
        captureStdout(hgPrefix + ['bisect', '--skip', options.skipRevs])

    labels = {}
    # Specify `hg bisect` ranges.
    if options.testInitialRevs:
        currRev = eRepo  # If testInitialRevs mode is set, compile and test the latest rev first.
    else:
        labels[sRepo] = ('good', 'assumed start rev is good')
        labels[eRepo] = ('bad', 'assumed end rev is bad')
        subprocess.check_call(hgPrefix + ['bisect', '-U', '-g', sRepo])
        currRev = getCsetHashFromBisectMsg(firstLine(
            captureStdout(hgPrefix + ['bisect', '-U', '-b', eRepo])[0]))

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
                print 'Skipped 20 times, stopping autoBisect.'
                break
        print label[0] + " (" + label[1] + ") ",

        if iterNum <= 0:
            print 'Finished testing the initial boundary revisions...',
        else:
            print "Bisecting for the n-th round where n is", iterNum, "and 2^n is", \
                    str(2**iterNum), "...",
        (blamedGoodOrBad, blamedRev, currRev, sRepo, eRepo) = \
            bisectLabel(hgPrefix, options, label[0], currRev, sRepo, eRepo)

        if options.testInitialRevs:
            options.testInitialRevs = False
            assert currRev is None
            currRev = sRepo  # If options.testInitialRevs is set, test earliest possible rev next.

        iterNum += 1
        endTime = time.time()
        oneRunTime = endTime - startTime
        print 'This iteration took %.3f seconds to run.' % oneRunTime

    if blamedRev is not None:
        checkBlameParents(repoDir, blamedRev, blamedGoodOrBad, labels, testRev, realStartRepo,
                          realEndRepo)

    vdump("Resetting bisect")
    subprocess.check_call(hgPrefix + ['bisect', '-U', '-r'])

    vdump("Resetting working directory")
    captureStdout(hgPrefix + ['update', '-r', 'default'], ignoreStderr=True)
    destroyPyc(repoDir)

    print dateStr()

def internalTestAndLabel(options):
    '''Use autoBisectJs without interestingness tests to examine the revision of the js shell.'''
    def inner(shellFilename, _hsHash):
        (stdoutStderr, exitCode) = testBinary(shellFilename, options.paramList,
            options.buildOptions.runWithVg, options.buildOptions.isThreadsafe)

        if (stdoutStderr.find(options.output) != -1) and (options.output != ''):
            return ('bad', 'Specified-bad output')
        elif options.watchExitCode != None and exitCode == options.watchExitCode:
            return ('bad', 'Specified-bad exit code ' + str(exitCode))
        elif options.watchExitCode == None and 129 <= exitCode <= 159:
            return ('bad', 'High exit code ' + str(exitCode))
        elif exitCode < 0:
            # On Unix-based systems, the exit code for signals is negative, so we check if
            # 128 + abs(exitCode) meets our specified signal exit code.
            if (options.watchExitCode != None and 128 - exitCode == options.watchExitCode):
                return ('bad', 'Specified-bad exit code ' + str(exitCode) + \
                        ' (after converting to signal)')
            elif (stdoutStderr.find(options.output) == -1) and (options.output != ''):
                return ('good', 'Bad output, but not the specified one')
            elif (options.watchExitCode != None and 128 - exitCode != options.watchExitCode):
                return ('good', 'Negative exit code, but not the specified one')
            else:
                return ('bad', 'Negative exit code ' + str(exitCode))
        elif exitCode == 0:
            return ('good', 'Exit code 0')
        elif (exitCode == 1 or exitCode == 2) and (options.output != '') and \
                (stdoutStderr.find('usage: js [') != -1 or \
                 stdoutStderr.find('Error: Short option followed by junk') != -1 or \
                 stdoutStderr.find('Error: Invalid long option:') != -1 or \
                 stdoutStderr.find('Error: Invalid short option:') != -1):
            return ('good', 'Exit code 1 or 2 - js shell quits ' + \
                            'because it does not support a given CLI parameter')
        elif 3 <= exitCode <= 6:
            return ('good', 'Acceptable exit code ' + str(exitCode))
        elif options.watchExitCode != None:
            return ('good', 'Unknown exit code ' + str(exitCode) + ', but not the specified one')
        else:
            return ('bad', 'Unknown exit code ' + str(exitCode))
    return inner

def externalTestAndLabel(options, interestingness):
    '''Make use of interestingness scripts to decide whether the changeset is good or bad.'''
    conditionScript = ximport.importRelativeOrAbsolute(interestingness[0])
    conditionArgPrefix = interestingness[1:]
    tempPrefix = os.path.join(mkdtemp(), "abExtTestAndLabel-")

    def inner(shellFilename, hsHash):
        conditionArgs = conditionArgPrefix + [shellFilename] + options.paramList
        if hasattr(conditionScript, "init"):
            # Since we're changing the js shell name, call init() again!
            conditionScript.init(conditionArgs)
        if conditionScript.interesting(conditionArgs, tempPrefix + hsHash):
            innerResult = ('bad', 'interesting')
        else:
            innerResult = ('good', 'not interesting')
        if os.path.isdir(tempPrefix + hsHash):
            shutil.rmtree(tempPrefix + hsHash)
        return innerResult
    return inner

def checkBlameParents(repoDir, blamedRev, blamedGoodOrBad, labels, testRev, startRepo, endRepo):
    """If bisect blamed a merge, try to figure out why."""

    bisectLied = False
    missedCommonAncestor = False

    parents = captureStdout(["hg", "-R", repoDir] + ["parent", '--template={node|short},',
                                                   "-r", blamedRev])[0].split(",")[:-1]

    if len(parents) == 1:
        return

    for p in parents:
        # Ensure we actually tested the parent.
        if labels.get(p) is None:
            print ""
            print ("Oops! We didn't test rev %s, a parent of the blamed revision! " + \
                "Let's do that now.") % str(p)
            if not isAncestor(repoDir, startRepo, p) and \
                    not isAncestor(repoDir, endRepo, p):
                print ('We did not test rev %s because it is not a descendant of either ' + \
                    '%s or %s.') % (str(p), startRepo, endRepo)
                # Note this in case we later decide the bisect result is wrong.
                missedCommonAncestor = True
            label = testRev(p)
            labels[p] = label
            print label[0] + " (" + label[1] + ") "
            print "As expected, the parent's label is the opposite of the blamed rev's label."

        # Check that the parent's label is the opposite of the blamed merge's label.
        if labels[p][0] == "skip":
            print "Parent rev %s was marked as 'skip', so the regression window includes it." % \
                    str(p)
        elif labels[p][0] == blamedGoodOrBad:
            print "Bisect lied to us! Parent rev %s was also %s!" % (str(p), blamedGoodOrBad)
            bisectLied = True
        else:
            assert labels[p][0] == {'good': 'bad', 'bad': 'good'}[blamedGoodOrBad]

    # Explain why bisect blamed the merge.
    if bisectLied:
        if missedCommonAncestor:
            ca = findCommonAncestor(repoDir, parents[0], parents[1])
            print ""
            print "Bisect blamed the merge because our initial range did not include one"
            print "of the parents."
            print "The common ancestor of %s and %s is %s." % (parents[0], parents[1], ca)
            label = testRev(ca)
            print label[0] + " (" + label[1] + ") "
            print "Consider re-running autoBisect with -s %s -e %s" % (ca, blamedRev)
            print "in a configuration where earliestWorking is before the common ancestor."
        else:
            print ""
            print "Most likely, bisect's result was unhelpful because one of the"
            print "tested revisions was marked as 'good' or 'bad' for the wrong reason."
            print "I don't know which revision was incorrectly marked. Sorry."
    else:
        print ""
        print "The bug was introduced by a merge (it was not present on either parent)."
        print "I don't know which patches from each side of the merge contributed to the bug. Sorry."

def sanitizeCsetMsg(msg, repo):
    '''Sanitizes changeset messages, removing email addresses.'''
    msgList = msg.split('\n')
    sanitizedMsgList = []
    for line in msgList:
        if line.find('<') != -1 and line.find('@') != -1 and line.find('>') != -1:
            line = ' '.join(line.split(' ')[:-1])
        elif line.startswith('changeset:') and 'mozilla-central' in repo:
            line = 'changeset:   http://hg.mozilla.org/mozilla-central/rev/' + line.split(':')[-1]
        sanitizedMsgList.append(line)
    return '\n'.join(sanitizedMsgList)

def bisectLabel(hgPrefix, options, hgLabel, currRev, startRepo, endRepo):
    '''Tell hg what we learned about the revision.'''
    assert hgLabel in ("good", "bad", "skip")
    outputResult = captureStdout(hgPrefix + ['bisect', '-U', '--' + hgLabel, currRev])[0]
    outputLines = outputResult.split("\n")

    repoDir = options.buildOptions.repoDir if options.buildOptions else options.browserOptions.repoDir

    if re.compile("Due to skipped revisions, the first (good|bad) revision could be any of:").match\
            (outputLines[0]):
        print('\n' + sanitizeCsetMsg(outputResult, repoDir) + '\n')
        return None, None, None, startRepo, endRepo

    r = re.compile("The first (good|bad) revision is:")
    m = r.match(outputLines[0])
    if m:
        print '\n\nautoBisect shows this is probably related to the following changeset:\n'
        print(sanitizeCsetMsg(outputResult, repoDir) + '\n')
        blamedGoodOrBad = m.group(1)
        blamedRev = getCsetHashFromBisectMsg(outputLines[1])
        return blamedGoodOrBad, blamedRev, None, startRepo, endRepo

    if options.testInitialRevs:
        return None, None, None, startRepo, endRepo

    # e.g. "Testing changeset 52121:573c5fa45cc4 (440 changesets remaining, ~8 tests)"
    vdump(outputLines[0])

    currRev = getCsetHashFromBisectMsg(outputLines[0])
    if currRev is None:
        print 'Resetting to default revision...'
        subprocess.check_call(hgPrefix + ['update', '-C', 'default'])
        destroyPyc(repoDir)
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


def bisectUsingLocalBuilds(options):
    '''
    Compiles binaries and bisects them locally.
    '''
    lockDir = os.path.join(ensureCacheDir(), 'autoBisectJs-lock')
    try:
        os.mkdir(lockDir)
    except OSError:
        print "autoBisect is already running"
        return
    try:
        if options.browserOptions:
            findBlamedCset(options, options.browserOptions.repoDir, buildBrowser.makeTestRev(options))
        else:
            findBlamedCset(options, options.buildOptions.repoDir, makeTestRev(options))
    finally:
        os.rmdir(lockDir)


#############################################
#  Bisection involving tinderbox js shells  #
#############################################


# From http://stackoverflow.com/a/3337198/3011305
class CustomDict(dict):
    def __getattr__(self, name):
        return self[name]


def bisectUsingTboxBins(options):
    '''
    Downloads tinderbox binaries and bisects them.
    '''
    # Note that the autoBisect lock directory is ignored if bisecting using tinderbox binaries.
    skippedIDs = []
    testedIDs = {}

    # Get list of tinderbox IDs
    # Note that "arch: None" will select the default architecture depending on the system.
    buildType = defaultBuildType(CustomDict(
        arch = None,
        compileType = options.buildOptions.compileType,
        repoName = options.nameOfTinderboxBranch,
    ))

    try:
        urlsTbox = getBuildList(buildType, earliestBuild=options.startRepo,
                                latestBuild=options.endRepo)
    except Exception, e:
        if 'The following exit code was returned: 8' in repr(e):
            print '\nYour branch name "' + options.nameOfTinderboxBranch + '" is likely invalid.',
            print 'Please choose a valid name, e.g. mozilla-central'
            sys.exit(1)
        else:
            raise

    # Download and test starting point.
    sID, startResult, sReason, sPosition, urlsTbox, skippedIDs, testedIDs = getAndTestMiddleBuild(
        options, 0, urlsTbox, buildType, skippedIDs, testedIDs)
    print 'Numeric ID ' + sID + ' was tested.'

    # Download and test ending point.
    eID, endResult, eReason, ePosition, urlsTbox, skippedIDs, testedIDs = getAndTestMiddleBuild(
        options, -1, urlsTbox, buildType, skippedIDs, testedIDs)
    print 'Numeric ID ' + eID + ' was tested.'

    if startResult == endResult:
        raise Exception('Starting and ending points should have opposite results')

    count = 0
    print '\nStarting bisection...\n'
    while True:
        vdump('Unsorted dictionary of tested IDs is: ' + str(testedIDs))
        count += 1
        print 'Test number ' + str(count) + ':'

        sortedUrlsTbox = sorted(urlsTbox)
        if len(sortedUrlsTbox) >= 3:
            mPosition = len(sortedUrlsTbox) // 2
        else:
            print '\nWARNING: ' + str(sortedUrlsTbox) + ' has size smaller than 3. ' + \
                'Impossible to return "middle" element.\n'
            mPosition = len(sortedUrlsTbox)

        # Test the middle revision. If it is not a complete build, test ones around it.
        mID, mResult, mReason, mPosition, urlsTbox, skippedIDs, testedIDs = getAndTestMiddleBuild(
            options, mPosition, urlsTbox, buildType, skippedIDs, testedIDs)

        # Refresh the range of tinderbox IDs depending on mResult.
        if mResult == endResult:
            urlsTbox = urlsTbox[0:(mPosition + 1)]
        else:
            urlsTbox = urlsTbox[(mPosition):len(urlsTbox)]

        print 'Numeric ID ' + mID + ' was tested.',

        # Exit infinite loop once we have tested both the starting point and the ending point.
        if len(urlsTbox) == 2 and (mID in testedIDs or mID in skippedIDs):
            break
        elif len(urlsTbox) < 2:
            print 'urlsTbox is: ' + str(urlsTbox)
            raise Exception('Length of urlsTbox should not be smaller than 2.')
        elif (len(testedIDs) - 2) > 30:
            raise Exception('Number of testedIDs has exceeded 30.')

        print showRemainingNumOfTests(urlsTbox)

    print
    vdump('Build URLs are: ' + str(urlsTbox))
    vdump('Skipped IDs are: ' + str(skippedIDs))
    assert getIdFromTboxUrl(urlsTbox[0]) in testedIDs, 'Starting ID should have been tested.'
    assert getIdFromTboxUrl(urlsTbox[1]) in testedIDs, 'Ending ID should have been tested.'
    outputTboxBisectionResults(options, urlsTbox, testedIDs)


def checkSaneCacheDirContents(cacheFolder):
    '''
    Checks that the cache directories do not have contents that conflict with one another.
    '''
    if os.path.isdir(cacheFolder):
        fList = os.listdir(cacheFolder)
        if 'build' in fList and 'incompleteBuild.txt' in fList:
            print cacheFolder + ' has subdirectories: ' + str(fList)
            raise Exception('Downloaded binaries and incompleteBuild.txt should not both be ' +\
                            'present together in this directory.')


def createTboxCacheFolder(cacheFolder):
    '''
    Attempt to create the tinderbox js shell's cache folder if it does not exist. If it does, check
    that its binaries are working properly.
    '''
    try:
        os.mkdir(cacheFolder)
    except OSError:
        isCacheBuildDirComplete = \
            os.path.isdir(normExpUserPath(os.path.join(cacheFolder, 'build', 'download'))) and \
            os.path.isdir(normExpUserPath(os.path.join(cacheFolder, 'build', 'dist')))
        try:
            testSaneJsBinary(cacheFolder)
        except AssertionError:
            # Build IDs with complete subfolders (both build/download and build/dist) should not
            # throw assertion failures.
            if isCacheBuildDirComplete:
                raise
        except Exception:
            # Remove build subdirectory of the numeric ID's cache folder if the
            # <tboxCacheFolder>/build/dist folder or <tboxCacheFolder>/build/download folder
            # do not exist. This will cause a re-download of the binaries.
            if os.path.isdir(normExpUserPath(os.path.join(cacheFolder, 'build'))) and \
                    not isCacheBuildDirComplete:
                shutil.rmtree(normExpUserPath(os.path.join(cacheFolder, 'build')))

    ensureCacheDirHasCorrectIdNum(cacheFolder)


def ensureCacheDirHasCorrectIdNum(cacheFolder):
    '''
    Ensures that the cache folder is named with the correct numeric ID.
    '''
    srcUrlPath = normExpUserPath(os.path.join(cacheFolder, 'build', 'download', 'source-url.txt'))
    if os.path.isfile(srcUrlPath):
        with open(srcUrlPath, 'rb') as f:
            fContents = f.read().splitlines()

        idNumFolderName = cacheFolder.split('-')[-1]
        idNumSourceUrl = fContents[0].split('/')[-2]

        assert idNumFolderName == idNumSourceUrl, 'Numeric ID in folder name (current value: ' + \
            idNumFolderName + ') has to be equal to the numeric ID from source URL ' + \
            '(current value: ' + idNumSourceUrl + ')'


def getAndTestMiddleBuild(options, index, urls, buildType, skippedIDs, testedIDs):
    '''
    Downloads, tests the build, returning the results and reason for failure (if any).
    '''
    isJsShell = (not options.browserOptions)
    idNum = getIdFromTboxUrl(urls[index])

    if index == 0 or index == -1:
        print '\nExamining ' + ('starting' if index == 0 else 'ending') + ' point...'

    tboxCacheFolder = normExpUserPath(os.path.join(ensureCacheDir(),
                                                   'tboxjs-' + buildType + '-' + idNum))
    createTboxCacheFolder(tboxCacheFolder)

    if os.path.isfile(getTboxJsBinPath(tboxCacheFolder)):
        print 'Found cached binary in: ' + tboxCacheFolder
    else:
        offset = 1
        subtotalTestedCount = 0

        prevNewIndex = newIndex = index

        lookedAtIncompleteBuildTxtFile = False

        breakOut = False
        while not breakOut:
            # These should remain within the loop as they get refreshed every iteration.
            incompleteBuildTxtFile = normExpUserPath(os.path.join(tboxCacheFolder,
                                                                  'incompleteBuild.txt'))
            incompleteBuildTxtContents = 'This build with numeric ID ' + idNum + ' is incomplete.'

            # Examine incompleteBuild.txt if it is present.
            if os.path.isfile(incompleteBuildTxtFile) and not lookedAtIncompleteBuildTxtFile:
                assert os.listdir(tboxCacheFolder) == ['incompleteBuild.txt'], 'Only ' + \
                    'incompleteBuild.txt should be present in ' + tboxCacheFolder
                with open(incompleteBuildTxtFile, 'rb') as f:
                    contentsF = f.read()
                    if not 'is incomplete.' in contentsF:
                        print 'Contents of ' + incompleteBuildTxtFile + ' is: ' + repr(contentsF)
                        raise Exception('Invalid incompleteBuild.txt file contents.')
                    else:
                        lookedAtIncompleteBuildTxtFile = True
                        print 'Examined build with numeric ID ' + idNum + ' to be incomplete. ' + \
                            'Trying another build...'

            # If incompleteBuild.txt is present, do not bother downloading again.
            if not lookedAtIncompleteBuildTxtFile:
                if downloadBuild(urls[index], tboxCacheFolder, jsShell=isJsShell):
                    assert os.listdir(tboxCacheFolder) == ['build'], 'Only ' + \
                        'the build subdirectory should be present in ' + tboxCacheFolder
                    try:
                        testSaneJsBinary(tboxCacheFolder)
                    except AssertionError:
                        raise
                    except Exception, e:
                        if 'Shell startup error' in repr(e):
                            if (index == 0 or index == -1):
                                print '\nWARNING: Unable to test ' + \
                                    ('starting' if index == 0 else 'ending') + \
                                    ' point due to a startup error.\n'
                                shutil.rmtree(tboxCacheFolder)
                                raise Exception('Unable to ascertain an initial regression or ' + \
                                                'fix window.')
                            else:
                                lookedAtIncompleteBuildTxtFile = writeIncompleteBuildTxtFile(
                                    tboxCacheFolder, incompleteBuildTxtFile,
                                    incompleteBuildTxtContents, idNum)
                                continue
                    breakOut = True
                    break
                else:
                    lookedAtIncompleteBuildTxtFile = writeIncompleteBuildTxtFile(tboxCacheFolder,
                        incompleteBuildTxtFile, incompleteBuildTxtContents, idNum)

            newIndex = index + offset

            # Remove skipped IDs from list of interesting URLs
            skippedIDs.append(idNum)
            # Try to avoid looping through everything by first checking for presence
            if idNum in str(urls):
                for entry in urls:
                    if idNum in entry:
                        urls.remove(entry)

            try:
                if urls[newIndex] in str(urls):
                    subtotalTestedCount += 1
            except IndexError:
                # Stop once we are testing beyond the start & end entries of the list
                if newIndex < 0 and prevNewIndex > len(urls):
                    breakOut = True
                    break
                elif prevNewIndex < 0 and newIndex > len(urls):
                    breakOut = True
                    break

                # Do not increment subtotalTestedCount if urls[newIndex] does not exist.
                newIndex = prevNewIndex  # Reset newIndex because newIndex will be out of bounds.

            offset = -offset if offset > 0 else -offset + 1

            # Refresh idNum and tboxCacheFolder
            idNum = getIdFromTboxUrl(urls[newIndex])
            tboxCacheFolder = normExpUserPath(os.path.join(ensureCacheDir(),
                                                           '-'.join(['tboxjs', buildType, idNum])))
            createTboxCacheFolder(tboxCacheFolder)
            checkSaneCacheDirContents(tboxCacheFolder)

            # Loop exit conditions
            if subtotalTestedCount > len(urls):
                breakOut = True  # Stop going out of range
                break
            elif idNum in testedIDs:
                breakOut = True  # Stop going after a tested ID.
                break
            elif os.path.isfile(getTboxJsBinPath(tboxCacheFolder)):
                breakOut = True  # Stop once we reach a numeric ID with a working js shell.
                break
            elif subtotalTestedCount > 30:
                raise Exception('Failed to find a working build after 30 tries.')

            prevNewIndex = newIndex

        if breakOut:
            index = newIndex

    checkSaneCacheDirContents(tboxCacheFolder)

    # Test the build only if it has not been tested before.
    if idNum not in testedIDs.keys():
        testedIDs[idNum] = getTimestampAndHashFromTboxFiles(tboxCacheFolder)
        print 'Testing binary...',
        result, reason = isTboxBinInteresting(options, tboxCacheFolder, testedIDs[idNum][1])
        print 'Result: ' + result + ' - ' + reason
        # Adds the result and reason to testedIDs
        testedIDs[idNum] = list(testedIDs[idNum]) + [result, reason]
    else:
        print 'Retrieving previous test result: ',
        result, reason = testedIDs[idNum][2:4]

    return idNum, result, reason, index, urls, skippedIDs, testedIDs


def getIdFromTboxUrl(url):
    '''
    Returns the numeric ID from the tinderbox URL at:
        https://ftp.mozilla.org/pub/mozilla.org/firefox/tinderbox-builds/
    '''
    return filter(None, url.split('/'))[-1]


def getTboxJsBinPath(baseDir):
    '''
    Returns the path to the tinderbox js binary from a download folder.
    '''
    return normExpUserPath(os.path.join(baseDir, 'build', 'dist', 'js.exe' if isWin else 'js'))


def getTimestampAndHashFromTboxFiles(folder):
    '''
    Returns timestamp and changeset information from the .txt file downloaded from tinderbox.
    '''
    downloadDir = normExpUserPath(os.path.join(folder, 'build', 'download'))
    for fn in os.listdir(downloadDir):
        if fn.startswith('firefox-') and fn.endswith('.txt'):
            with open(os.path.join(downloadDir, fn), 'rb') as f:
                fContents = f.read().splitlines()
            break
    assert len(fContents) == 2, 'Contents of the .txt file should only have 2 lines'
    return fContents[0], fContents[1].split('/')[-1]


def isTboxBinInteresting(options, downloadDir, csetHash):
    '''
    Test the required tinderbox binary.
    '''
    return options.testAndLabel(getTboxJsBinPath(downloadDir), csetHash)


def outputTboxBisectionResults(options, interestingList, testedBuildsDict):
    '''
    Returns formatted bisection results from using tinderbox builds.
    '''
    sTimestamp, sHash, sResult, sReason = testedBuildsDict[getIdFromTboxUrl(interestingList[0])]
    eTimestamp, eHash, eResult, eReason = testedBuildsDict[getIdFromTboxUrl(interestingList[1])]

    print '\nParameters for compilation bisection:'
    pOutput = '-p "' + options.parameters + '"' if options.parameters != '-e 42' else ''
    oOutput = '-o "' + options.output + '"' if options.output is not '' else ''
    params = filter(None, ['-s ' + sHash, '-e ' + eHash, pOutput, oOutput, '-b <build parameters>'])
    print ' '.join(params)

    print '\n=== Tinderbox Build Bisection Results by autoBisect ===\n'
    print 'The "' + sResult + '" changeset has the timestamp "' + sTimestamp + \
        '" and the hash "' + sHash + '".'
    print 'The "' + eResult + '" changeset has the timestamp "' + eTimestamp + \
        '" and the hash "' + eHash + '".'

    # Formulate hgweb link for mozilla repositories
    hgWebAddrList = ['hg.mozilla.org']
    if options.nameOfTinderboxBranch == 'mozilla-central':
        hgWebAddrList.append(options.nameOfTinderboxBranch)
    elif options.nameOfTinderboxBranch == 'mozilla-inbound':
        hgWebAddrList.extend(['integration', options.nameOfTinderboxBranch])
    elif options.nameOfTinderboxBranch == 'mozilla-aurora' or \
            options.nameOfTinderboxBranch == 'mozilla-beta' or \
            options.nameOfTinderboxBranch == 'mozilla-release' or \
            'mozilla-esr' in options.nameOfTinderboxBranch:
        hgWebAddrList.extend(['releases', options.nameOfTinderboxBranch])
    hgWebAddr = 'https://' + '/'.join(hgWebAddrList)

    if sResult == 'good' and eResult == 'bad':
        windowType = 'regression'
    elif sResult == 'bad' and eResult == 'good':
        windowType = 'fix'
    else:
        raise Exception('Unknown windowType because starting result is "' + sResult + '" and ' + \
                        'ending result is "' + eResult + '".')
    print '\nLikely ' + windowType + ' window: ' + hgWebAddr + '/pushloghtml?fromchange=' + sHash +\
            '&tochange=' + eHash + '\n'


def showRemainingNumOfTests(reqList):
    '''
    Display the approximate number of tests remaining.
    '''
    remainingTests = int(math.ceil(math.log(len(reqList), 2))) - 1
    wordTest = 'tests'
    if remainingTests == 1:
        wordTest = 'test'
    return '~' + str(remainingTests) + ' ' + wordTest + ' remaining...\n'


def testSaneJsBinary(cacheFolder):
    '''
    If the cache folder is present, check that the js binary is working properly.
    '''
    assert os.path.isdir(normExpUserPath(os.path.join(cacheFolder, 'build', 'download')))
    assert os.path.isdir(normExpUserPath(os.path.join(cacheFolder, 'build', 'dist')))
    assert os.path.isfile(normExpUserPath(os.path.join(cacheFolder, 'build', 'dist',
                                                       'js' + ('.exe' if isWin else ''))))
    try:
        out, retCode = captureStdout([getTboxJsBinPath(cacheFolder), '-e', '42'],
            ignoreExitCode=True)
        # Exit code -1073741515 on Windows seems to show up when a required DLL is not present.
        # This was testable at the time of writing, see bug 953314.
        isDllNotPresentWinStartupError = (isWin and retCode == -1073741515)
        # We should have another condition here for non-Windows platforms but we do not yet have
        # a situation where we can test broken tinderbox js shells on those platforms.
        if isDllNotPresentWinStartupError:
            print 'Shell startup error - a .dll file is probably not present.'
            raise
        elif retCode != 0:
            print 'Non-zero return code: ' + str(retCode)
            raise
        return True  # js binary is sane
    except AssertionError:
        raise
    except Exception:
        # Remove build subdirectory of the numeric ID's cache folder if shell does not work well.
        # This will cause a re-download of the binaries.
        shutil.rmtree(normExpUserPath(os.path.join(cacheFolder, 'build')))
        if isDllNotPresentWinStartupError:
            raise Exception('Shell startup error')


def writeIncompleteBuildTxtFile(cacheFolder, txtFile, txtContents, num):
    '''
    Writes a text file indicating that this particular build is incomplete.
    '''
    if os.path.isdir(normExpUserPath(os.path.join(cacheFolder, 'build', 'dist'))) or \
            os.path.isdir(normExpUserPath(os.path.join(cacheFolder, 'build', 'download'))):
        shutil.rmtree(normExpUserPath(os.path.join(cacheFolder, 'build')))
    assert not os.path.isfile(txtFile), 'incompleteBuild.txt should not be present.'
    with open(txtFile, 'wb') as f:
        f.write(txtContents)
    print 'Wrote a text file that indicates numeric ID ' + num + ' has an incomplete build.'
    return False  # False indicates that this text file has not yet been looked at.


def main():
    '''Prevent running two instances of autoBisectJs concurrently - we don't want to confuse hg.'''
    sanityChecks()
    options = parseOpts()
    if options.useTinderboxBinaries:
        bisectUsingTboxBins(options)
    else:
        bisectUsingLocalBuilds(options)

if __name__ == '__main__':
    # Reopen stdout, unbuffered. This is similar to -u. From http://stackoverflow.com/a/107717
    sys.stdout = Unbuffered(sys.stdout)
    main()

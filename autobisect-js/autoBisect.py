#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import platform
import re
import shutil
import subprocess
import sys
import time

from optparse import OptionParser
from tempfile import mkdtemp

from knownBrokenEarliestWorking import knownBrokenRanges, earliestKnownWorkingRev

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'interestingness'))
sys.path.append(path1)
import ximport
path2 = os.path.abspath(os.path.join(path0, os.pardir, 'js'))
sys.path.append(path2)
from compileShell import CompiledShell, makeTestRev, ensureCacheDir
from inspectShell import constructVgCmdList, testBinary
path3 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path3)
from fileManipulation import firstLine
import buildOptions
from hgCmds import findCommonAncestor, getCsetHashFromBisectMsg, getMcRepoDir, getRepoHashAndId, \
    getRepoNameFromHgrc, isAncestor
from subprocesses import captureStdout, dateStr, isVM, normExpUserPath, Unbuffered, verbose, vdump

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
        repoDir = getMcRepoDir()[1],
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
    )

    # Specify how the shell will be built.
    # See buildOptions.py for details.
    parser.add_option('-b', '--build',
                      dest='buildOptions',
                      help='Specify build options, e.g. -b "-c opt --arch=32" (python buildOptions.py --help)')

    # Specify the repository (working directory) in which to bisect.
    parser.add_option('-R', '--repoDir', dest='repoDir',
                      help='Source code directory. Defaults to "%default".')
    parser.add_option('--resetToTipFirst', dest='resetRepoFirst',
                      action='store_true',
                      help='First reset to default tip overwriting all local changes. ' + \
                           'Equivalent to first executing `hg update -C default`. ' + \
                           'Defaults to "%default".')

    # Specify the revisions between which to bisect.
    parser.add_option('-s', '--startRev', dest='startRepo',
                      help='Earliest changeset to consider (usually a "good" cset). Defaults to the ' + \
                           'earliest revision known to work at all.')
    parser.add_option('-e', '--endRev', dest='endRepo',
                      help='Latest changeset to consider (usually a "bad" cset). Defaults to the head of the main branch, "default".')
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

    (options, args) = parser.parse_args()
    options.buildOptions = buildOptions.parseShellOptions(options.buildOptions)

    options.paramList = [normExpUserPath(x) for x in options.parameters.split(' ') if x]
    assert options.compilationFailedLabel in ('bad', 'good', 'skip')

    options.repoDir = normExpUserPath(options.repoDir)
    assert getRepoNameFromHgrc(options.repoDir) != '', 'Not a valid Mercurial repository!'

    extraFlags = []

    if options.useInterestingnessTests:
        if len(args) < 1:
            print 'args are: ' + args
            parser.error('Not enough arguments.')
        for a in args:
            if a.startswith("--flags="):
                extraFlags = a[8:].split(' ')
        options.testAndLabel = externalTestAndLabel(options, args)
    else:
        if len(args) >= 1:
            parser.error('Too many arguments.')
        options.testAndLabel = internalTestAndLabel(options)

    if options.startRepo is None:
        options.startRepo = earliestKnownWorkingRev(options.buildOptions, options.paramList + extraFlags)

    if len(sys.argv) < 2:
        print "Note: since no arguments were specified, we're just ensuring the shell does not crash on startup/shutdown."

    return options

def findBlamedCset():
    print dateStr()

    options = parseOpts()

    hgPrefix = ['hg', '-R', options.repoDir]

    # Resolve names such as "tip", "default", or "52707" to stable hg hash ids, e.g. "9f2641871ce8".
    realStartRepo = sRepo = getRepoHashAndId(options.repoDir, repoRev=options.startRepo)[0]
    realEndRepo = eRepo = getRepoHashAndId(options.repoDir, repoRev=options.endRepo)[0]
    vdump("Bisecting in the range " + sRepo + ":" + eRepo)

    # Refresh source directory (overwrite all local changes) to default tip if required.
    if options.resetRepoFirst:
        subprocess.check_call(hgPrefix + ['up', '-C', 'default'])
         # Throws exit code 255 if purge extension is not enabled in .hgrc:
        subprocess.check_call(hgPrefix + ['purge', '--all'])

    # Reset bisect ranges and set skip ranges.
    captureStdout(hgPrefix + ['bisect', '-r'])
    captureStdout(hgPrefix + ['bisect', '--skip', ' + '.join(knownBrokenRanges())])

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

    testRev = makeTestRev(options)

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
        checkBlameParents(options.repoDir, blamedRev, blamedGoodOrBad, labels, testRev, realStartRepo,
                          realEndRepo)

    vdump("Resetting bisect")
    subprocess.check_call(hgPrefix + ['bisect', '-U', '-r'])

    vdump("Resetting working directory")
    captureStdout(hgPrefix + ['up', '-r', 'default'], ignoreStderr=True)

    print dateStr()

def internalTestAndLabel(options):
    '''Use autoBisectJs without interestingness tests to examine the revision of the js shell.'''
    def inner(shellFilename, _hgHash):
        (stdoutStderr, exitCode) = testBinary(shellFilename, options.paramList,
                                              options.buildOptions.runWithVg)

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

    def inner(shellFilename, hgHash):
        conditionArgs = conditionArgPrefix + (constructVgCmdList() if options.buildOptions.runWithVg else []) +\
                            [shellFilename] + options.paramList
        if hasattr(conditionScript, "init"):
            # Since we're changing the js shell name, call init() again!
            conditionScript.init(conditionArgs)
        if conditionScript.interesting(conditionArgs, tempPrefix + hgHash):
            innerResult = ('bad', 'interesting')
        else:
            innerResult = ('good', 'not interesting')
        if os.path.isdir(tempPrefix + hgHash):
            shutil.rmtree(tempPrefix + hgHash)
        return innerResult
    return inner

def checkBlameParents(repoDir, blamedRev, blamedGoodOrBad, labels, testRev, startRepo, endRepo):
    """Ensure we actually tested the parents of the blamed revision."""
    parents = captureStdout(["hg", "-R", repoDir] + ["parent", '--template={node|short},',
                                                   "-r", blamedRev])[0].split(",")[:-1]
    bisectLied = False
    for p in parents:
        testedLastMinute = False
        if labels.get(p) is None:
            print ""
            print ("Oops! We didn't test rev %s, a parent of the blamed revision! " + \
                "Let's do that now.") % str(p)
            if not isAncestor(repoDir, startRepo, p) and \
                    not isAncestor(repoDir, endRepo, p):
                print ('We did not test rev %s because it is not a descendant of either ' + \
                    '%s or %s.') % (str(p), startRepo, endRepo)
            label = testRev(p)
            labels[p] = label
            print label[0] + " (" + label[1] + ") "
            testedLastMinute = True
        if labels[p][0] == "skip":
            print "Parent rev %s was marked as 'skip', so the regression window includes it." % \
                    str(p)
        elif labels[p][0] == blamedGoodOrBad:
            print "Bisect lied to us! Parent rev %s was also %s!" % (str(p), blamedGoodOrBad)
            bisectLied = True
        else:
            if verbose or testedLastMinute:
                print "As expected, the parent's label is the opposite of the blamed rev's label."
            assert labels[p][0] == {'good': 'bad', 'bad': 'good'}[blamedGoodOrBad]
    if len(parents) == 2 and bisectLied:
        print ""
        print "Perhaps we should expand the search to include the common ancestor of the " + \
            "blamed changeset's parents."
        ca = findCommonAncestor(repoDir, parents[0], parents[1])
        print "The common ancestor of %s and %s is %s." % (parents[0], parents[1], ca)
        label = testRev(ca)
        print label[0] + " (" + label[1] + ") "
        print 'The following line is still under testing:'
        print "Try setting -s to %s, and -e to %s, and re-run autoBisect." % (ca, endRepo)

def sanitizeCsetMsg(msg):
    '''Sanitizes changeset messages, removing email addresses.'''
    msgList = msg.split('\n')
    sanitizedMsgList = []
    for line in msgList:
        if line.find('<') != -1 and line.find('@') != -1 and line.find('>') != -1:
            line = ' '.join(line.split(' ')[:-1])
        sanitizedMsgList.append(line)
    return '\n'.join(sanitizedMsgList)

def bisectLabel(hgPrefix, options, hgLabel, currRev, startRepo, endRepo):
    '''Tell hg what we learned about the revision.'''
    assert hgLabel in ("good", "bad", "skip")
    outputResult = captureStdout(hgPrefix + ['bisect', '-U', '--' + hgLabel, currRev])[0]
    outputLines = outputResult.split("\n")

    if re.compile("Due to skipped revisions, the first (good|bad) revision could be any of:").match\
            (outputLines[0]):
        print('\n' + sanitizeCsetMsg(outputResult) + '\n')
        return None, None, None, startRepo, endRepo

    r = re.compile("The first (good|bad) revision is:")
    m = r.match(outputLines[0])
    if m:
        print '\n\nautoBisect shows this is probably related to the following changeset:\n'
        print(sanitizeCsetMsg(outputResult) + '\n')
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
        subprocess.check_call(hgPrefix + ['up', '-C', 'default'])
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

def main():
    '''Prevent running two instances of autoBisectJs concurrently - we don't want to confuse hg.'''
    sanityChecks()
    lockDir = os.path.join(ensureCacheDir(), 'autoBisectJs-lock')
    try:
        os.mkdir(lockDir)
    except OSError:
        print "autoBisect is already running"
        return
    try:
        findBlamedCset()
    finally:
        os.rmdir(lockDir)

if __name__ == '__main__':
    # Reopen stdout, unbuffered. This is similar to -u. From http://stackoverflow.com/a/107717
    sys.stdout = Unbuffered(sys.stdout)
    main()

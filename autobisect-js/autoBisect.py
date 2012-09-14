#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import platform
import shutil
import subprocess
import sys
import re
import tempfile
from copy import deepcopy
from optparse import OptionParser
from types import *

from knownBrokenEarliestWorking import earliestKnownWorkingRev, knownBrokenRanges

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'interestingness'))
sys.path.append(path1)
import ximport

path2 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path2)
from subprocesses import captureStdout, dateStr, isLinux, isMac, isWin, isVM, macVer, \
    normExpUserPath, shellify, vdump

path3 = os.path.abspath(os.path.join(path0, os.pardir, 'js'))
sys.path.append(path3)
from compileShell import autoconfRun
from countCpus import cpuCount

verbose = False

# autoBisect uses temporary directory python APIs. On WinXP, these are located at
# c:\docume~1\mozilla\locals~1\temp\ and the ~ in the shortened folders break pymake.
# This can be fixed by moving compilations to autobisect-cache, but we lose the benefit of
# compiling in a temporary directory. Not worth it, for an OS that is on its way out.
#assert platform.uname()[2] != 'XP'
# Disable autoBisect when running in a VM, even Linux. This has the possibility of interacting with
# the repositories in the trees directory as they can update to a different changeset within the VM.
# It should work when running manually though.
assert isVM()[1] == False

shellCacheDirStart = os.path.join('c:', os.sep) if isVM() == ('Windows', True) \
    else os.path.join('~', 'Desktop')
# This particular machine has insufficient disk space on the main drive.
if isLinux and os.path.exists(os.sep + 'hddbackup'):
    shellCacheDirStart = os.path.join(os.sep + 'hddbackup' + os.sep)
shellCacheDir = normExpUserPath(os.path.join(shellCacheDirStart, 'autobisect-cache'))
if not os.path.exists(shellCacheDir):
    os.mkdir(shellCacheDir)

def main():
    print dateStr()
    global hgPrefix
    global shellCacheDir

    # Parse options and parameters from the command-line.
    options = parseOpts()
    (compileType, sourceDir, stdoutOutput, resetBool, startRepo, endRepo, paranoidBool, \
     archNum, flagsRequired, watchExitCode, valgrindSupport, testAndLabel, compilationFailedLabel) = options

    sourceDir = os.path.expanduser(sourceDir)
    hgPrefix = ['hg', '-R', sourceDir]
    if startRepo is None:
        startRepo = earliestKnownWorkingRev(flagsRequired, archNum, valgrindSupport)

    # Resolve names such as "tip", "default", or "52707" to stable hg hash ids
    # such as "9f2641871ce8".
    realStartRepo = startRepo = hgId(startRepo)
    realEndRepo = endRepo = hgId(endRepo)

    vdump("Bisecting in the range " + startRepo + ":" + endRepo)

    # Refresh source directory (overwrite all local changes) to default tip if required.
    if resetBool:
        subprocess.call(hgPrefix + ['up', '-C', 'default'])
        # Make sure you've enabled the extension in your ".hgrc" file.
        subprocess.call(hgPrefix + ['purge', '--all'])

    labels = {}
    captureStdout(hgPrefix + ['bisect', '-r'])
    captureStdout(hgPrefix + ['bisect', '--skip', " + ".join(knownBrokenRanges())])

    # Specify `hg bisect` ranges.
    if paranoidBool:
        currRev = startRepo
    else:
        labels[startRepo] = ('good', 'assumed start rev is good')
        labels[endRepo] = ('bad', 'assumed end rev is bad')
        captureStdout(hgPrefix + ['bisect', '-U', '-g', startRepo])
        currRev = extractChangesetFromMessage(firstLine(captureStdout(hgPrefix + ['bisect', '-U', '-b', endRepo])[0]))

    testRev = makeTestRev(shellCacheDir, sourceDir, archNum, compileType, valgrindSupport, testAndLabel, compilationFailedLabel)

    iterNum = 1
    if paranoidBool:
        iterNum -= 2

    skipCount = 0
    blamedRev = None

    while currRev is not None:
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
            print "Paranoid test finished..."
        else:
            print "Bisecting for the n-th round where n is", iterNum, "and 2^n is", str(2**iterNum), "..."
        (currRev, blamedGoodOrBad, blamedRev, startRepo, endRepo) = bisectLabel(label[0], currRev, startRepo, endRepo, paranoidBool)

        if paranoidBool:
            paranoidBool = False
            assert currRev is None
            currRev = endRepo

        iterNum += 1

    if blamedRev is not None:
        checkBlameParents(blamedRev, blamedGoodOrBad, labels, testRev, realStartRepo, realEndRepo)

    vdump("Resetting bisect")
    subprocess.call(hgPrefix + ['bisect', '-U', '-r'])

    vdump("Resetting working directory")
    captureStdout(hgPrefix + ['up', '-r', 'default'], ignoreStderr=True)

    print dateStr()

def findCommonAncestor(a, b):
    # Requires hg 1.6 for the revset feature
    return captureStdout(hgPrefix + ["log", "--template={node|short}", "-r", "ancestor("+a+","+b+")"])[0]

def isAncestor(a, b):
    return findCommonAncestor(a, b) == a

def checkBlameParents(blamedRev, blamedGoodOrBad, labels, testRev, startRepo, endRepo):
    """Ensure we actually tested the parents of the blamed revision."""
    parents = captureStdout(hgPrefix + ["parent", '--template={node|short},', "-r", blamedRev])[0].split(",")[:-1]
    bisectLied = False
    for p in parents:
        testedLastMinute = False
        if labels.get(p) is None:
            print ""
            print "Oops! We didn't test rev %s, a parent of the blamed revision! Let's do that now." % p
            if not isAncestor(startRepo, p) and not isAncestor(endRepo, p):
                print "We did not test rev %s because it is not a descendant of either %s or %s." % (p, startRepo, endRepo)
            label = testRev(p)
            labels[p] = label
            print label[0] + " (" + label[1] + ") "
            testedLastMinute = True
        if labels[p][0] == "skip":
            print "Parent rev %s was marked as 'skip', so the regression window includes it."
        elif labels[p][0] == blamedGoodOrBad:
            print "Bisect lied to us! Parent rev %s was also %s!" % (p, blamedGoodOrBad)
            bisectLied = True
        else:
            if verbose or testedLastMinute:
                print "As expected, the parent's label is the opposite of the blamed rev's label."
            assert labels[p][0] == {'good': 'bad', 'bad': 'good'}[blamedGoodOrBad]
    if len(parents) == 2 and bisectLied:
        print ""
        print "Perhaps we should expand the search to include the common ancestor of the blamed changeset's parents."
        ca = findCommonAncestor(parents[0], parents[1])
        print "The common ancestor of %s and %s is %s." % (parents[0], parents[1], ca)
        label = testRev(ca)
        print label[0] + " (" + label[1] + ") "
        #print "Try setting -s to %s, and -e to %s, and re-run autoBisect." % (ca, parents[0])

def makeTestRev(shellCacheDir, sourceDir, archNum, compileType, valgrindSupport, testAndLabel, compilationFailedLabel):
    def testRev(rev):
        cachedShell = os.path.join(shellCacheDir, shellName(archNum, compileType, rev, valgrindSupport))
        cachedNoShell = cachedShell + ".busted"

        print "Rev " + rev + ":",
        if os.path.exists(cachedShell):
            jsShellName = cachedShell
            print "Found cached shell...   ",
        elif os.path.exists(cachedNoShell):
            return (compilationFailedLabel, 'compilation failed (cached)')
        else:
            print "Updating...",
            captureStdout(hgPrefix + ['update', '-r', rev], ignoreStderr=True)
            try:
                print "Compiling...",
                jsShellName = makeShell(shellCacheDir, sourceDir,
                                        archNum, compileType, valgrindSupport,
                                        rev)
            except Exception, e:
                open(cachedNoShell, 'w').close()
                return (compilationFailedLabel, 'compilation failed (' + str(e) + ')')

        print "Testing...",
        return testAndLabel(jsShellName, rev)
    return testRev

def internalTestAndLabel(filename, flagsRequired, valgrindSupport, stdoutOutput, watchExitCode):
    def inner(jsShellName, rev):
        (stdoutStderr, exitCode) = testBinary(jsShellName, filename, flagsRequired, valgrindSupport)

        if (stdoutStderr.find(stdoutOutput) != -1) and (stdoutOutput != ''):
            return ('bad', 'Specified-bad output')
        elif watchExitCode != None and exitCode == watchExitCode:
            return ('bad', 'Specified-bad exit code ' + str(exitCode))
        elif watchExitCode == None and 129 <= exitCode <= 159:
            return ('bad', 'High exit code ' + str(exitCode))
        elif exitCode < 0:
            # On Unix-based systems, the exit code for signals is negative,
            # so we check if 128 + abs(exitCode) meets our specified signal
            # exit code.
            if (watchExitCode != None and 128 - exitCode == watchExitCode):
                return ('bad', 'Specified-bad exit code ' + str(exitCode) + ' (after converting to signal)')
            else:
                return ('bad', 'Negative exit code ' + str(exitCode))
        elif exitCode == 0:
            return ('good', 'Exit code 0')
        elif (exitCode == 1 or exitCode == 2) and \
                (stdoutStderr.find('usage: js [') != -1 or \
                 stdoutStderr.find('Error: Invalid short option:') != -1) and \
                (stdoutOutput != ''):
            return ('good', 'Exit code 1 or 2 - js shell quits because it does not support a given CLI parameter')
        elif 3 <= exitCode <= 6:
            return ('good', 'Acceptable exit code ' + str(exitCode))
        elif watchExitCode != None:
            return ('good', 'Unknown exit code ' + str(exitCode) + ', but not the specified one')
        else:
            return ('bad', 'Unknown exit code ' + str(exitCode))
    return inner

def externalTestAndLabel(filename, flagsRequired, interestingness):
    conditionScript = ximport.importRelativeOrAbsolute(interestingness[0])
    conditionArgPrefix = interestingness[1:]

    tempPrefix = os.path.join(tempfile.mkdtemp(), "x")

    def inner(jsShellName, rev):
        conditionArgs = conditionArgPrefix + [jsShellName] + flagsRequired + [filename]
        if hasattr(conditionScript, "init"):
            # Since we're changing the js shell name, call init() again!
            conditionScript.init(conditionArgs)
        if conditionScript.interesting(conditionArgs, tempPrefix + rev):
            return ('bad', 'interesting')
        else:
            return ('good', 'not interesting')
    return inner

def parseOpts():
    usage = 'Usage: %prog [options] filename'
    parser = OptionParser(usage)
    # See http://docs.python.org/library/optparse.html#optparse.OptionParser.disable_interspersed_args
    parser.disable_interspersed_args()

    if isVM() == ('Windows', True):
        mcRepoDirStart = os.path.join('z:', os.sep)
    elif isVM() == ('Linux', True):
        mcRepoDirStart = os.path.join('/', 'mnt', 'hgfs')
    else:
        mcRepoDirStart = '~'
    mcRepoDir = normExpUserPath(os.path.join(mcRepoDirStart, 'trees', 'mozilla-central'))
    # Define the repository (working directory) in which to bisect.
    parser.add_option('-R', '--repoDir',
                      dest='dir',
                      default=mcRepoDir,
                      help='Source code directory. Defaults to "%default"')
    parser.add_option('-r', '--resetToTipFirstBool',
                      dest='resetBool',
                      action='store_true',
                      default=False,
                      help='First reset to default tip overwriting all local changes. ' + \
                           'Equivalent to first executing `hg update -C default`. ' + \
                           'Defaults to "%default"')

    # Define the revisions between which to bisect.
    # If you want to find out when a problem *went away*, give -s the later revision and -e an earlier revision,
    # or use -p (in which case the order doesn't matter).
    parser.add_option('-s', '--start',
                      dest='startRepo',
                      help='Initial good revision (usually the earliest). Defaults to the earliest revision known to work at all.')
    parser.add_option('-e', '--end',
                      dest='endRepo',
                      default='default',
                      help='Initial bad revision (usually the latest). Defaults to "%default"')
    parser.add_option('-p', '--paranoid',
                      dest='paranoidBool',
                      action='store_true',
                      default=False,
                      help='Test the -s and -e revisions (rather than automatically treating them as -g and -b).')

    # Define the type of build to test.
    parser.add_option('-a', '--architecture',
                      dest='archi',
                      type='choice',
                      choices=['32', '64'],
                      help='Test architecture. Only accepts "32" or "64"')
    parser.add_option('-c', '--compileType',
                      dest='compileType',
                      type='choice',
                      choices=['dbg', 'opt'],
                      default='dbg',
                      help='js shell compile type. Defaults to "%default"')

    # Define specific type of failure to look for (optional).
    parser.add_option('-o', '--output',
                      dest='output',
                      default='',
                      help='Stdout or stderr output to be observed. Defaults to "%default". ' + \
                           'For assertions, set to "ssertion fail"')
    parser.add_option('-w', '--watchExitCode',
                      dest='watchExitCode',
                      type='int',
                      default=None,
                      help='Look out for a specific exit code. Only this exit code will be considered bad.')
    parser.add_option('-i', '--interestingness',
                      dest='interestingnessBool',
                      default=False,
                      action="store_true",
                      help="Interpret the final arguments as an interestingness test")

    # Define parameters to be passed to the binary.
    parser.add_option('--flags',
                      dest='flagsRequired',
                      default='',
                      help='Define the flags to reproduce the bug, e.g. "-m,-j". ' + \
                           'Defaults to "%default"')

    parser.add_option('--compilation-failed-label',
                      dest='compilationFailedLabel',
                      default='skip',
                      help='How to treat revisions that fail to compile (bad, good, or skip). ' + \
                           'Defaults to "%default"')

    # Enable valgrind support.
    parser.add_option('-v', '--valgrind',
                      dest='valgSupport',
                      action='store_true',
                      default=False,
                      help='Enable valgrind support. Defaults to "%default"')

    (options, args) = parser.parse_args()

    assert options.compilationFailedLabel in ("bad", "good", "skip")

    flagsReqList = filter(None, options.flagsRequired.split(','))

    if len(args) < 1:
        parser.error('Not enough arguments')
    filename = args[0]

    if options.interestingnessBool:
        if len(args) < 2:
            parser.error('Not enough arguments.')
        testAndLabel = externalTestAndLabel(filename, flagsReqList, args[1:])
    else:
        if len(args) >= 2:
            parser.error('Too many arguments.')
        testAndLabel = internalTestAndLabel(filename, flagsReqList, options.valgSupport, options.output, options.watchExitCode)


    return options.compileType, options.dir, options.output, \
            options.resetBool, options.startRepo, options.endRepo, options.paranoidBool, options.archi, \
            flagsReqList, options.watchExitCode, options.valgSupport, testAndLabel, options.compilationFailedLabel

def hgId(rev):
    return captureStdout(hgPrefix + ['log', '--template={node|short}', '-r', rev])[0]

def extractChangesetFromMessage(str):
    # For example, a bisect message like "Testing changeset 41831:4f4c01fb42c3 (2 changesets remaining, ~1 tests)"
    r = re.compile(r"(^|.* )(\d+):(\w{12}).*")
    m = r.match(str)
    if m:
        return m.group(3)

assert extractChangesetFromMessage("x 12345:abababababab") == "abababababab"
assert extractChangesetFromMessage("x 12345:123412341234") == "123412341234"
assert extractChangesetFromMessage("12345:abababababab y") == "abababababab"

def makeShell(shellCacheDir, sourceDir, archNum, compileType, valgrindSupport, currRev):
    tempDir = tempfile.mkdtemp(prefix="abc-" + currRev + "-")
    compileJsSrcPath = normExpUserPath(os.path.join(tempDir, 'compilePath', 'js', 'src'))

    vdump("Compiling in " + tempDir)

    # Copy the js tree.
    jsSrcDir = normExpUserPath(os.path.join(sourceDir, 'js', 'src'))
    if sys.version_info >= (2, 6):
        shutil.copytree(jsSrcDir, compileJsSrcPath,
                        ignore=shutil.ignore_patterns(
                            # ignore_patterns does not work in Python 2.5.
                            'jit-test', 'tests', 'trace-test', 'xpconnect'))
    else:
        shutil.copytree(jsSrcDir, compileJsSrcPath)
    jsPubSrcDir = normExpUserPath(os.path.join(sourceDir, 'js', 'public'))
    if os.path.isdir(jsPubSrcDir):
        shutil.copytree(jsPubSrcDir, os.path.join(compileJsSrcPath, '..', 'public'))
    mfbtSrcDir = normExpUserPath(os.path.join(sourceDir, 'mfbt'))
    if os.path.isdir(mfbtSrcDir):
        shutil.copytree(mfbtSrcDir, os.path.join(compileJsSrcPath, '..', '..', 'mfbt'))

    # Run autoconf.
    autoconfRun(compileJsSrcPath)

    # Create objdir within the compileJsSrcPath.
    objdir = os.path.join(compileJsSrcPath, compileType + '-objdir')
    os.mkdir(objdir)

    # Run configure.
    threadsafe = False  # Let's disable support for threadsafety in the js shell
    cfgPath = normExpUserPath(os.path.join(compileJsSrcPath, 'configure'))
    cfgJsBin(archNum, compileType, threadsafe, cfgPath, objdir)

    # Compile and copy the first binary.
    try:
        # Only pymake was tested on Windows.
        shell = compileCopy(archNum, compileType, currRev, isWin, sourceDir, shellCacheDir, objdir, valgrindSupport)
    finally:
        assert os.path.isdir(tempDir) is True
        vdump('Removing ' + tempDir)
        shutil.rmtree(tempDir)
        assert os.path.isdir(tempDir) is False
    return shell

# Run the testcase on the compiled js binary.
def testBinary(shell, testFile, flagsRequired, valgSupport):
    # Normalize the path to the testFile because of slash/backslash issues on Windows.
    testBinaryCmd = [shell] + flagsRequired + [normExpUserPath(testFile)]
    if valgSupport:
        valgPrefixCmd = []
        valgPrefixCmd.append('valgrind')
        if isMac:
            valgPrefixCmd.append('--dsymutil=yes')
        valgPrefixCmd.append('--smc-check=all-non-file')
        valgPrefixCmd.append('--leak-check=full')
        testBinaryCmd = valgPrefixCmd + testBinaryCmd
    vdump('The testing command is: ' + shellify(testBinaryCmd))

    # Capture stdout and stderr into the same string.
    p = subprocess.Popen(testBinaryCmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    retCode = p.returncode
    if verbose:
        print 'The exit code is:', retCode
        if len(out) > 0:
            print 'stdout shows:', out
        if len(err) > 0:
            print 'stderr shows:', err

    # Switch to interactive input mode similar to `cat testcase.js | ./js -j -i`.
    # Doesn't work, stdout shows:
    #can't open : No such file or directory
    #The exit code is: 4
    #The second output is: None
    #if retCode == 0:
    #    # Append the quit() function to make the testcase quit.
    #    # Doesn't work if retCode is something other than 0, that watchExitCode specified.
    #    testcaseFile = open(file, 'a')
    #    testcaseFile.write('\nquit()\n')
    #    testcaseFile.close()
    #
    #    # Test interactive input.
    #    print 'Switching to interactive input mode in case passing as a CLI ' + \
    #            'argument does not reproduce the issue..'
    #    testBinaryCmd3 = subprocess.Popen([shell, methodJit, tracingJit, '-i'],
    #        stdin=(subprocess.Popen(['cat', file])).stdout)
    #    output2 = testBinaryCmd3.communicate()[0]
    #    retCode = testBinaryCmd3.returncode
    #    print 'The exit code is:', retCode
    #    print 'The second output is:', output2
    return out + "\n" + err, retCode

def bisectLabel(hgLabel, currRev, startRepo, endRepo, ignoreResult):
    '''Tell hg what we learned about the revision.'''
    assert hgLabel in ("good", "bad", "skip")

    outputResult = captureStdout(hgPrefix + ['bisect', '-U', '--' + hgLabel, currRev])[0]
    outputLines = outputResult.split("\n")

    if re.compile("Due to skipped revisions, the first (good|bad) revision could be any of:").match(outputLines[0]):
        print outputResult
        return None, None, None, startRepo, endRepo

    r = re.compile("The first (good|bad) revision is:")
    m = r.match(outputLines[0])
    if m:
        print '\nautoBisect shows this is probably related to the following changeset:\n'
        print outputResult
        blamedGoodOrBad = m.group(1)
        blamedRev = extractChangesetFromMessage(outputLines[1])
        return None, blamedGoodOrBad, blamedRev, startRepo, endRepo

    if ignoreResult:
        return None, None, None, startRepo, endRepo

    # e.g. "Testing changeset 52121:573c5fa45cc4 (440 changesets remaining, ~8 tests)"
    vdump(outputLines[0])

    currRev = extractChangesetFromMessage(outputLines[0])
    if currRev is None:
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

    return currRev, None, None, start, end

def firstLine(s):
    return s.split('\n')[0]

def cfgJsBin(archNum, compileType, threadsafe, configure, objdir):
    '''
    This function configures a js binary depending on the parameters.
    '''
    cfgCmdList = []
    cfgEnvDt = deepcopy(os.environ)
    origCfgEnvDt = deepcopy(os.environ)
    # For tegra Ubuntu, no special commands needed, but do install Linux prerequisites,
    # do not worry if build-dep does not work, also be sure to apt-get zip as well.
    if (archNum == '32') and (os.name == 'posix') and (os.uname()[1] != 'tegra-ubuntu'):
        # 32-bit shell on Mac OS X 10.6 Snow Leopard and greater, install Xcode 4 for SL.
        if isMac:
            assert macVer() >= [10, 6]  # We no longer support Leopard 10.5 and prior.
            cfgEnvDt['CC'] = 'clang -Qunused-arguments -fcolor-diagnostics -arch i386'
            cfgEnvDt['CXX'] = 'clang++ -Qunused-arguments -fcolor-diagnostics -arch i386'
            cfgEnvDt['HOST_CC'] = 'clang -Qunused-arguments -fcolor-diagnostics'
            cfgEnvDt['HOST_CXX'] = 'clang++ -Qunused-arguments -fcolor-diagnostics'
            cfgEnvDt['RANLIB'] = 'ranlib'
            cfgEnvDt['AR'] = 'ar'
            cfgEnvDt['AS'] = '$CC'
            cfgEnvDt['LD'] = 'ld'
            cfgEnvDt['STRIP'] = 'strip -x -S'
            cfgEnvDt['CROSS_COMPILE'] = '1'
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(configure))
            cfgCmdList.append('--target=i386-apple-darwin9.2.0')  # Leopard 10.5.2
            cfgCmdList.append('--enable-macos-target=10.5')
        # 32-bit shell on 32/64-bit x86 Linux
        elif isLinux and (os.uname()[4] != 'armv7l'):
            # apt-get `ia32-libs gcc-multilib g++-multilib` first, if on 64-bit Linux.
            cfgEnvDt['PKG_CONFIG_LIBDIR'] = '/usr/lib/pkgconfig'
            cfgEnvDt['CC'] = 'gcc -m32'
            cfgEnvDt['CXX'] = 'g++ -m32'
            cfgEnvDt['AR'] = 'ar'
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(configure))
            cfgCmdList.append('--target=i686-pc-linux')
        # 32-bit shell on ARM (non-tegra ubuntu)
        elif os.uname()[4] == 'armv7l':
            cfgEnvDt['CC'] = '/opt/cs2007q3/bin/gcc'
            cfgEnvDt['CXX'] = '/opt/cs2007q3/bin/g++'
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(configure))
        else:
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(configure))
    # 64-bit shell on Mac OS X 10.7 Lion and greater
    elif isMac and macVer() >= [10, 7] and archNum == '64':
        cfgEnvDt['CC'] = 'clang -Qunused-arguments -fcolor-diagnostics'
        cfgEnvDt['CXX'] = 'clang++ -Qunused-arguments -fcolor-diagnostics'
        cfgEnvDt['AR'] = 'ar'
        cfgCmdList.append('sh')
        cfgCmdList.append(os.path.normpath(configure))
        cfgCmdList.append('--target=x86_64-apple-darwin11.4.0')  # Lion 10.7.4
    elif isWin and archNum == '64':
        cfgCmdList.append('sh')
        cfgCmdList.append(os.path.normpath(configure))
        cfgCmdList.append('--host=x86_64-pc-mingw32')
        cfgCmdList.append('--target=x86_64-pc-mingw32')
    else:
        cfgCmdList.append('sh')
        cfgCmdList.append(os.path.normpath(configure))

    if compileType == 'dbg':
        cfgCmdList.append('--disable-optimize')
        cfgCmdList.append('--enable-debug')
    elif compileType == 'opt':
        cfgCmdList.append('--enable-optimize')
        cfgCmdList.append('--disable-debug')
        cfgCmdList.append('--enable-profiling')  # needed to obtain backtraces on opt shells
        cfgCmdList.append('--enable-gczeal')
        cfgCmdList.append('--enable-debug-symbols')  # gets debug symbols on opt shells

    cfgCmdList.append('--enable-methodjit')  # Enabled by default now, but useful for autoBisect
    cfgCmdList.append('--enable-type-inference') # Enabled by default now, but useful for autoBisect
    # Fuzzing tweaks for more useful output, implemented in bug 706433
    cfgCmdList.append('--enable-more-deterministic')
    cfgCmdList.append('--disable-tests')
    # See bug 773746. Enabling this breaks autoBisect for versions prior to 7aba0b7a805f
    #cfgCmdList.append('--enable-root-analysis')

    if threadsafe:
        cfgCmdList.append('--enable-threadsafe')
        cfgCmdList.append('--with-system-nspr')
    # Works-around "../editline/libeditline.a: No such file or directory" build errors by using
    # readline instead of editline.
    #cfgCmdList.append('--enable-readline')

    if os.name == 'posix':
        if (isLinux and (os.uname()[4] != 'armv7l')) or isMac:
            cfgCmdList.append('--enable-valgrind')
            if isLinux:
                cfgCmdList.append('--with-ccache')  # ccache does not seem to work on Mac.
        # ccache is not applicable for non-Tegra Ubuntu ARM builds.
        elif os.uname()[1] == 'tegra-ubuntu':
            cfgCmdList.append('--with-ccache')
            cfgCmdList.append('--with-arch=armv7-a')
    else:
        # Only tested to work for pymake in Windows.
        counter = 0
        for entry in cfgCmdList:
            if os.sep in entry:
                assert isWin  # MozillaBuild on Windows sometimes confuses "/" and "\".
                cfgCmdList[counter] = cfgCmdList[counter].replace(os.sep, '\\\\')
            counter = counter + 1

    # Print whatever we added to the environment
    envVarList = []
    for envVar in set(cfgEnvDt.keys()) - set(origCfgEnvDt.keys()):
        strToBeAppended = envVar + '="' + cfgEnvDt[envVar] + '"' \
            if ' ' in cfgEnvDt[envVar] else envVar + '=' + cfgEnvDt[envVar]
        envVarList.append(strToBeAppended)
    vdump('Environment variables added are: ' + ' '.join(envVarList))

    out = captureStdout(cfgCmdList, ignoreStderr=True, currWorkingDir=objdir, env=cfgEnvDt)

    return out, envVarList, cfgEnvDt, cfgCmdList

def shellName(archNum, compileType, extraID, vgSupport):
    osName = 'windows' if isWin else platform.system().lower()
    sname = '-'.join(x for x in ['js', compileType, archNum, "vg" if vgSupport else "", extraID,
                                 osName] if x)
    ext = '.exe' if isWin else ''
    return sname + ext

def compileCopy(archNum, compileType, extraID, usePymake, repoDir, destDir, objDir, vgSupport):
    '''
    This function compiles and copies a binary.
    '''
    # Replace cpuCount() with multiprocessing's cpu_count() once Python 2.6 is in all build slaves.
    jobs = ((cpuCount() * 5) // 4) if cpuCount() > 2 else 3
    compiledNamePath = normExpUserPath(
        os.path.join(objDir, 'js' + ('.exe' if isWin else '')))
    try:
        cmdList = []
        ignoreECode = False
        if usePymake:
            cmdList = ['python', '-OO',
                     os.path.normpath(os.path.join(repoDir, 'build', 'pymake', 'make.py')),
                     '-j' + str(jobs), '-s']
        else:
            cmdList = ['make', '-C', objDir, '-s']
            ignoreECode = True
            if os.name == 'posix':
                cmdList.append('-j' + str(jobs))  # Win needs pymake for multicore compiles.
        vdump('cmdList from compileCopy is: ' + ' '.join(cmdList))
        out = captureStdout(cmdList, combineStderr=True, ignoreExitCode=ignoreECode,
                            currWorkingDir=objDir)[0]
        if usePymake and 'no such option: -s' in out:  # Retry only for this situation.
            cmdList.remove('-s')  # Pymake older than m-c rev 232553f741a0 did not support '-s'.
            print 'Trying once more without -s...'
            vdump('cmdList from compileCopy is: ' + ' '.join(cmdList))
            out = captureStdout(cmdList, combineStderr=True, ignoreExitCode=ignoreECode,
                                currWorkingDir=objDir)[0]
    except Exception, e:
        # Sometimes a non-zero error can be returned during the make process, but eventually a
        # shell still gets compiled.
        if os.path.exists(compiledNamePath):
            print 'A shell was compiled even though there was a non-zero exit code. Continuing...'
        else:
            raise Exception("`make` did not result in a js shell, '" + repr(e) + "' thrown.")

    if not os.path.exists(compiledNamePath):
        print out
        raise Exception("`make` did not result in a js shell, no exception thrown.")
    else:
        newNamePath = normExpUserPath(
            os.path.join(destDir, shellName(archNum, compileType, extraID, vgSupport)))
        shutil.copy2(compiledNamePath, newNamePath)
        return newNamePath

def lockedMain():
    """Prevent running two instances of autoBisect at once, because we don't want to confuse hg."""
    lockDir = os.path.join(shellCacheDir, "autobisect-lock")
    try:
        os.mkdir(lockDir)
    except OSError, e:
        print "autoBisect is already running"
        return
    try:
        main()
    finally:
        os.rmdir(lockDir)

if __name__ == '__main__':
    # Reopen stdout, unbuffered.
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
    lockedMain()

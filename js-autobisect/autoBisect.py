#!/usr/bin/env python

#/* ***** BEGIN LICENSE BLOCK	****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is autoBisect.
#
# The Initial Developer of the Original Code is
# Gary Kwong.
# Portions created by the Initial Developer are Copyright (C) 2006-2008
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
# Jesse Ruderman
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# * ***** END LICENSE BLOCK	****	/

import os, shutil, subprocess, sys, re, tempfile
from optparse import OptionParser

path0 = os.path.dirname(sys.argv[0])
path1 = os.path.abspath(os.path.join(path0, "..", "lithium"))
sys.path.append(path1)
import ximport
path2 = os.path.abspath(os.path.join(path0, "..", "jsfunfuzz"))
sys.path.append(path2)
from fnStartjsfunfuzz import *

verbose = False
COMPILATION_FAILED_LABEL = 'skip'

shellCacheDir = os.path.join(os.path.expanduser("~"), "Desktop", "autobisect-cache")
if not os.path.exists(shellCacheDir):
    os.mkdir(shellCacheDir)

def main():
    global hgPrefix
    global shellCacheDir

    # Do not support Windows XP because the ~ folder is in "/Documents and Settings/",
    # which contains spaces. This breaks MinGW, which is what MozillaBuild uses.
    # From Windows Vista onwards, the folder is in "/Users/".
    # Edit 2: Don't support Windows till XP is deprecated, and when we create fuzzing
    # directories in ~-land instead of in /c/. We lack permissions when we move from
    # /c/ to ~-land in Vista/7.
    # Edit 3: Windows 7 is now supported if directories are in ~-land.
    # Edit 4: Windows 7 SP1 is also supported.
    if os.name == 'nt':
        if platform.uname()[3] != '6.1.7600' and platform.uname()[3] != '6.1.7601':
            raise Exception('autoBisect is not supported on Windows versions lower than Windows 7.')

    # Parse options and parameters from the command-line.
    options = parseOpts()
    (compileType, sourceDir, stdoutOutput, resetBool, startRepo, endRepo, paranoidBool, \
     archNum, tracingjitBool, methodjitBool, watchExitCode, valgrindSupport, testAndLabel) = options

    sourceDir = os.path.expanduser(sourceDir)
    hgPrefix = ['hg', '-R', sourceDir]
    if startRepo is None:
        startRepo = earliestKnownWorkingRev(tracingjitBool, methodjitBool, archNum, valgrindSupport)

    # Resolve names such as "tip", "default", or "52707" to stable hg hash ids
    # such as "9f2641871ce8".
    realStartRepo = startRepo = hgId(startRepo)
    realEndRepo = endRepo = hgId(endRepo)

    if verbose:
        print "Bisecting in the range " + startRepo + ":" + endRepo

    # Refresh source directory (overwrite all local changes) to default tip if required.
    if resetBool:
        subprocess.call(hgPrefix + ['up', '-C', 'default'])
        # XXX should also "hg purge" here, but "purge" is an extension.

    labels = {}

    # Reset `hg bisect`
    captureStdout(hgPrefix + ['bisect', '-r'])

    # Skip some busted revisions.
    # It might make sense to avoid (or note) these in checkBlameParents.
    # 1. descendants(eae8350841be) - descendants(f3e58c264932) [partial]
    # Note: The following instructions are untested.
    # To add to the list of descendant revsets:
    # - Temporarily set COMPILATION_FAILED_LABEL in autoBisect.py to 'bad' instead of 'skip'
    # - Then take one of the revs that fails, say fd756976e52c
    # - 404.js does not need to exist, but assuming tip / default works,
    # - (1) will tell you when the brokenness started
    # - (1) autoBisect.py -p -a32 -s fd756976e52c 404.js
    # - (2) will tell you when the brokenness ended
    # - (2) autoBisect.py -p -a32 -e fd756976e52c 404.js
    # Alternative: (descendants(last good changeset)-descendants(first working changeset))
    captureStdout(hgPrefix + ['bisect', '--skip', 'eae8350841be'])
    captureStdout(hgPrefix + ['bisect', '--skip', 'e5958cd4a135'])
    captureStdout(hgPrefix + ['bisect', '--skip', 'd575f16c7f55']) # an ill-timed merge into the jaegermonkey repository!
    captureStdout(hgPrefix + ['bisect', '--skip', '0d5d2ceb9436'])
    captureStdout(hgPrefix + ['bisect', '--skip', 'e6496cd735a6'])
    captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(8de0a7fef2c0)-descendants(d43e89d8a20b))'], ignoreStderr=True, ignoreExitCode=True) # early jaeger
    captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(a6c636740fb9)-descendants(ca11457ed5fe))'], ignoreStderr=True, ignoreExitCode=True) # a large backout
    captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(c12c8651c10d)-descendants(723d44ef6eed))'], ignoreStderr=True, ignoreExitCode=True) # m-c to tm merge that broke compilation

    # Specify `hg bisect` ranges.
    if paranoidBool:
        currRev = startRepo
    else:
        labels[startRepo] = ('good', 'assumed start rev is good')
        labels[endRepo] = ('bad', 'assumed end rev is bad')
        captureStdout(hgPrefix + ['bisect', '-U', '-g', startRepo])
        currRev = extractChangesetFromMessage(firstLine(captureStdout(hgPrefix + ['bisect', '-U', '-b', endRepo])))

    testRev = makeTestRev(shellCacheDir, sourceDir, archNum, compileType, tracingjitBool, methodjitBool, valgrindSupport, testAndLabel)

    while currRev is not None:
        label = testRev(currRev)
        labels[currRev] = label
        print label[0] + " (" + label[1] + ") ",

        print "Bisecting..."
        (currRev, blamedGoodOrBad, blamedRev, startRepo, endRepo) = bisectLabel(label[0], currRev, startRepo, endRepo, paranoidBool)

        if paranoidBool:
            paranoidBool = False
            assert currRev is None
            currRev = endRepo

    if blamedRev is not None:
        checkBlameParents(blamedRev, blamedGoodOrBad, labels, testRev, realStartRepo, realEndRepo)

    if verbose:
        print "Resetting bisect"
    subprocess.call(hgPrefix + ['bisect', '-U', '-r'])

    if verbose:
        print "Resetting working directory"
    captureStdout(hgPrefix + ['up', '-r', 'default'], ignoreStderr=True)

def findCommonAncestor(a, b):
    # Requires hg 1.6 for the revset feature
    return captureStdout(hgPrefix + ["log", "--template={node|short}", "-r", "ancestor("+a+","+b+")"])

def isAncestor(a, b):
    return findCommonAncestor(a, b) == a

def checkBlameParents(blamedRev, blamedGoodOrBad, labels, testRev, startRepo, endRepo):
    """Ensure we actually tested the parents of the blamed revision."""
    parents = captureStdout(hgPrefix + ["parent", '--template={node|short},', "-r", blamedRev]).split(",")[:-1]
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

def makeTestRev(shellCacheDir, sourceDir, archNum, compileType, tracingjitBool, methodjitBool, valgrindSupport, testAndLabel):
    def testRev(rev):
        cachedShell = os.path.join(shellCacheDir, shellName(archNum, compileType, rev, valgrindSupport))
        cachedNoShell = cachedShell + ".busted"

        print "Rev " + rev + ":",
        if os.path.exists(cachedShell):
            jsShellName = cachedShell
            print "Found cached shell...   ",
        elif os.path.exists(cachedNoShell):
            return (COMPILATION_FAILED_LABEL, 'compilation failed (cached)')
        else:
            print "Updating...",
            captureStdout(hgPrefix + ['update', '-r', rev], ignoreStderr=True)
            try:
                print "Compiling...",
                jsShellName = makeShell(shellCacheDir, sourceDir,
                                        archNum, compileType, tracingjitBool, methodjitBool, valgrindSupport,
                                        rev)
            except Exception as e:
                open(cachedNoShell, 'w').close()
                return (COMPILATION_FAILED_LABEL, 'compilation failed (' + str(e) + ')')

        print "Testing...",
        return testAndLabel(jsShellName, rev)
    return testRev

def internalTestAndLabel(filename, methodjitBool, tracingjitBool, valgrindSupport, stdoutOutput, watchExitCode):
    def inner(jsShellName, rev):
        (stdoutStderr, exitCode) = testBinary(jsShellName, filename, methodjitBool,
                                              tracingjitBool, valgrindSupport)

        if (stdoutStderr.find(stdoutOutput) != -1) and (stdoutOutput != ''):
            return ('bad', 'Specified-bad output')
        elif exitCode == watchExitCode:
            return ('bad', 'Specified-bad exit code ' + str(exitCode))
        elif 129 <= exitCode <= 159:
            return ('bad', 'High exit code ' + str(exitCode))
        elif exitCode < 0:
            return ('bad', 'Negative exit code ' + str(exitCode))
        elif exitCode == 0:
            return ('good', 'Exit code 0')
        elif 3 <= exitCode <= 6:
            return ('good', 'Acceptable exit code ' + str(exitCode))
        else:
            return ('bad', 'Unknown exit code ' + str(exitCode))
    return inner

def externalTestAndLabel(filename, methodjitBool, tracingjitBool, interestingness):
    engineFlags = []
    if tracingjitBool:
        engineFlags = engineFlags + ["-j"]
    if methodjitBool:
        engineFlags = engineFlags + ["-m"]

    conditionScript = ximport.importRelativeOrAbsolute(interestingness[0])
    conditionArgPrefix = interestingness[1:]

    tempPrefix = os.path.join(tempfile.mkdtemp(), "x")

    def inner(jsShellName, rev):
        conditionArgs = conditionArgPrefix + [jsShellName] + engineFlags + [filename]
        conditionScript.init(conditionArgs) # !!!
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

    # Define the repository (working directory) in which to bisect.
    parser.add_option('-d', '--dir',
                      dest='dir',
                      default=os.path.expanduser('~/tracemonkey/'),
                      help='Source code directory. Defaults to "~/tracemonkey/"')
    parser.add_option('-r', '--resetToTipFirstBool',
                      dest='resetBool',
                      action='store_true',
                      default=False,
                      help='First reset to default tip overwriting all local changes. ' + \
                           'Equivalent to first executing `hg update -C default`. ' + \
                           'Defaults to "False"')

    # Define the revisions between which to bisect.
    # If you want to find out when a problem *went away*, give -s the later revision and -e an earlier revision,
    # or use -p (in which case the order doesn't matter).
    parser.add_option('-s', '--start',
                      dest='startRepo',
                      help='Initial good revision (usually the earliest). Defaults to the earliest revision known to work at all.')
    parser.add_option('-e', '--end',
                      dest='endRepo',
                      default='default',
                      help='Initial bad revision (usually the latest). Defaults to "default"')
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
                      help='js shell compile type. Defaults to "dbg"')

    # Define specific type of failure to look for (optional).
    parser.add_option('-o', '--output',
                      dest='output',
                      default='',
                      help='Stdout or stderr output to be observed. Defaults to "". ' + \
                           'For assertions, set to "ssertion fail"')
    parser.add_option('-w', '--watchExitCode',
                      dest='watchExitCode',
                      type='choice',
                      choices=['3', '4', '5', '6'],
                      help='Look out for a specific exit code in the range [3,6]')
    parser.add_option('-i', '--interestingness',
                      dest='interestingnessBool',
                      default=False,
                      action="store_true",
                      help="Interpret the final arguments as an interestingness test")

    # Define parameters to be passed to the binary.
    parser.add_option('-j', '--tracingjit',
                      dest='tracingjitBool',
                      action='store_true',
                      default=False,
                      help='Enable -j, tracing JIT when autoBisecting. Defaults to "False"')
    parser.add_option('-m', '--methodjit',
                      dest='methodjitBool',
                      action='store_true',
                      default=False,
                      help='Enable -m, method JIT when autoBisecting. Defaults to "False"')

    # Enable valgrind support.
    parser.add_option('-v', '--valgrind',
                      dest='valgSupport',
                      action='store_true',
                      default=False,
                      help='Enable valgrind support. Defaults to "False"')

    (options, args) = parser.parse_args()

    # Only WinXP/Vista/7, Linux and Mac OS X 10.6.x are supported. This is what
    # the osCheck() function checks. Though, Windows platforms are already unsupported.
    osCheck()

    if options.watchExitCode:
        options.watchExitCode = int(options.watchExitCode)

    if len(args) < 1:
        parser.error('Not enough arguments')
    filename = args[0]

    if options.interestingnessBool:
        if len(args) < 2:
            parser.error('Not enough arguments.')
        testAndLabel = externalTestAndLabel(filename, options.methodjitBool, options.tracingjitBool, args[1:])
    else:
        if len(args) >= 2:
            parser.error('Too many arguments.')
        testAndLabel = internalTestAndLabel(filename, options.methodjitBool, options.tracingjitBool, options.valgSupport, options.output, options.watchExitCode)


    return options.compileType, options.dir, options.output, \
            options.resetBool, options.startRepo, options.endRepo, options.paranoidBool, options.archi, \
            options.tracingjitBool, options.methodjitBool, options.watchExitCode, \
            options.valgSupport, testAndLabel

def hgId(rev):
    return captureStdout(hgPrefix + ["id", "-i", "-r", rev])

def earliestKnownWorkingRev(tracingjitBool, methodjitBool, archNum, valgrindSupport):
    """Returns the oldest version of the shell that can run jsfunfuzz."""
    # Unfortunately, there are also interspersed runs of brokenness, such as:
    # * 0c8d4f846be8::bfb330182145 (~28226::28450).
    # * 1558cef8a8a0::e81fa1f189dc (~51206::51210 plus merges) (see bug 590519) ('rdtsc' was not declared in this scope)
    # * dd0b2f4d5299::???????????? (perhaps 64-bit only)
    # To make matters worse, merges between mozilla-central and tracemonkey might have happened during
    # the brokenness, resulting in a large number of additional broken changesets
    # in "descendants(x) - descendants(y)".
    # We don't deal with those at all, and --skip does not get out of such messes quickly.

    snowLeopardOrHigher = (platform.system() == 'Darwin') and (platform.mac_ver()[0].split('.') >= ['10', '6'])

    if False and profilejitBool:
        return '339457364540' # ~55724 on TM, first rev that has the -p option
    elif methodjitBool:
        if os.name == 'nt':
            return '9f2641871ce8' # ~52707 on TM, first rev that can run with pymake and -m
        else:
            return '547af2626088' # ~52268 on TM, first rev that can run jsfunfuzz-n.js with -m
    elif os.name == 'nt':
        return 'ea59b927d99f' # ~46545 on TM, first rev that can run pymake on Windows with most recent set of instructions
    elif snowLeopardOrHigher and archNum == "64":
        return "1a44373ccaf6" # ~32547 on TM, config.guess change for snow leopard
    elif snowLeopardOrHigher and archNum == "32":
        return "db4d22859940" # ~24564 on TM, imacros compilation change
    elif valgrindSupport:
        return "582a62c8f910" # ~21412 on TM, fixed a regexp valgrind warning that is triggered by an empty jsfunfuzz testcase
    else:
        return "8c52a9486c8f" # ~21110 on TM, switch from Makefile.ref to autoconf

def extractChangesetFromMessage(str):
    # For example, a bisect message like "Testing changeset 41831:4f4c01fb42c3 (2 changesets remaining, ~1 tests)"
    r = re.compile(r"(^|.* )(\d+):(\w{12}).*")
    m = r.match(str)
    if m:
        return m.group(3)

assert extractChangesetFromMessage("x 12345:abababababab") == "abababababab"
assert extractChangesetFromMessage("x 12345:123412341234") == "123412341234"
assert extractChangesetFromMessage("12345:abababababab y") == "abababababab"

def makeShell(shellCacheDir, sourceDir, archNum, compileType, tracingjitBool, methodjitBool, valgrindSupport, currRev):
    tempDir = tempfile.mkdtemp(prefix="abc-" + currRev + "-")
    compilePath = os.path.join(tempDir, "compilePath")

    if verbose:
        print "Compiling in " + tempDir

    # Copy the js tree.
    cpJsTreeDir(sourceDir, compilePath)

    # Run autoconf.
    autoconfRun(compilePath)

    # Create objdir within the compilePath.
    objdir = os.path.join(compilePath, compileType + '-objdir')
    os.mkdir(objdir)

    # Run configure.
    threadsafe = False  # Let's disable support for threadsafety in the js shell
    osCheck()
    cfgJsBin(archNum, compileType,
                      True, True, # always *build* with both JITs enabled
                      valgrindSupport,
                      threadsafe, os.path.join(compilePath, 'configure'), objdir)

    # Compile and copy the first binary.
    # Only pymake was tested on Windows.
    usePymake = True if os.name == 'nt' else False
    shell = compileCopy(archNum, compileType, currRev, usePymake, shellCacheDir, objdir, valgrindSupport)
    rmDirInclSubDirs(tempDir)
    return shell

# Run the testcase on the compiled js binary.
def testBinary(shell, file, methodjitBool, tracingjitBool, valgSupport):
    methodJit = ['-m'] if methodjitBool else []
    tracingJit = ['-j'] if tracingjitBool else []
    testBinaryCmd = [shell] + methodJit + tracingJit + [file]
    if valgSupport:
        testBinaryCmd = ['valgrind'] + testBinaryCmd
    if verbose:
        print 'The testing command is:', ' '.join(testBinaryCmd)

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

    outputResult = captureStdout(hgPrefix + ['bisect', '-U', '--' + hgLabel, currRev])
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

    if verbose:
        # e.g. "Testing changeset 52121:573c5fa45cc4 (440 changesets remaining, ~8 tests)"
        print outputLines[0]

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

# This function removes a directory along with its subdirectories.
def rmDirInclSubDirs(dir):
    #print 'Removing ' + dir
    shutil.rmtree(dir)

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

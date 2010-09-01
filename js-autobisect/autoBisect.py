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
path2 = os.path.abspath(os.path.join(path0, "..", "jsfunfuzz"))
sys.path.append(path2)
from fnStartjsfunfuzz import *

verbose = False

def main():
    global hgPrefix

    # Do not support Windows XP because the ~ folder is in "/Documents and Settings/",
    # which contains spaces. This breaks MinGW, which is what MozillaBuild uses.
    # From Windows Vista onwards, the folder is in "/Users/".
    # Edit 2: Don't support Windows till XP is deprecated, and when we create fuzzing
    # directories in ~-land instead of in /c/. We lack permissions when we move from
    # /c/ to ~-land in Vista/7.
    if os.name == 'nt':
        raise Exception('autoBisect is not supported on Windows.')

    # Parse options and parameters from the command-line.
    filename = sys.argv[-1:][0]
    options = parseOpts()
    (compileType, sourceDir, stdoutOutput, resetBool, startRepo, endRepo, \
     archNum, tracingjitBool, methodjitBool, watchExitCode, valgrindSupport) = options

    sourceDir = os.path.expanduser(sourceDir)
    hgPrefix = ['hg', '-R', sourceDir]
    if startRepo is None:
        startRepo = earliestKnownWorkingRev(tracingjitBool, methodjitBool, archNum)

    # Resolve names such as "tip", "default", or "9f2641871ce8" to numeric hg ids such as "52707".
    startRepo = hgId(startRepo)
    endRepo = hgId(endRepo)

    if verbose:
        print "Bisecting in the range " + str(startRepo) + ":" + str(endRepo)

    # Refresh source directory (overwrite all local changes) to default tip if required.
    if resetBool:
        subprocess.call(hgPrefix + ['up', '-C', 'default'])

    shellCacheDir = os.path.join(os.path.expanduser("~"), "Desktop", "autobisect-cache")
    if not os.path.exists(shellCacheDir):
        os.mkdir(shellCacheDir)

    # Specify `hg bisect` ranges.
    captureStdout(hgPrefix + ['bisect', '-r'])
    # If in "bug" mode, this startRepo changeset does not exhibit the issue.
    captureStdout(hgPrefix + ['bisect', '-U', '-g', str(startRepo)])
    # If in "bug" mode, this endRepo changeset exhibits the issue.
    bisectMessage = firstLine(captureStdout(hgPrefix + ['bisect', '-U', '-b', str(endRepo)]))

    # Find out the number of tests to be executed based on the initial hg bisect output.
    initialTestCountEstimate = checkNumOfTests(bisectMessage)
    currRev = extractChangesetFromBisectMessage(bisectMessage)

    while currRev is not None:
        result = None
        cachedShell = os.path.join(shellCacheDir, shellName(archNum, compileType, str(currRev)))
        jsShellName = None
        label = None
        
        print "Rev " + str(currRev) + ":",
        if os.path.exists(cachedShell):
            jsShellName = cachedShell
            print "Found cached shell...",
        else:
            print "Updating...",
            captureStdout(hgPrefix + ['update', '-r', str(currRev)], ignoreStderr=True)
            try:
                print "Compiling...",
                jsShellName = makeShell(shellCacheDir, sourceDir, 
                                        archNum, compileType, tracingjitBool, methodjitBool, valgrindSupport, 
                                        currRev)
            except Exception as e:
                label = ('skip', 'compilation failed (' + str(e) + ')')

        if jsShellName:
            print "Testing...",
            label = testAndLabel(jsShellName, filename, methodjitBool, tracingjitBool, valgrindSupport, stdoutOutput, watchExitCode)

        print label[0] + " (" + label[1] + ") ",

        print "Bisecting..."
        (currRev, startRepo, endRepo) = bisectLabel(label[0], currRev, startRepo, endRepo)

    if verbose:
        print "Resetting bisect"
    subprocess.call(hgPrefix + ['bisect', '-U', '-r'])

    if verbose:
        print "Resetting working directory"
    captureStdout(hgPrefix + ['up', '-r', 'default'], ignoreStderr=True)

def testAndLabel(jsShellName, filename, methodjitBool, tracingjitBool, valgrindSupport, stdoutOutput, watchExitCode):
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
    # Simply reverse these two options if you want to find out when a problem went away.
    parser.add_option('-s', '--start',
                      dest='startRepo',
                      help='Earlist revision to consider. Defaults to a guess.')
    parser.add_option('-e', '--end',
                      dest='endRepo',
                      default='default',
                      help='Latest revision to consider. Defaults to "default"')

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
    # Check for a correct number of arguments.
    if len(args) != 1:
        parser.error('There is a wrong number of arguments.')

    if options.watchExitCode:
        options.watchExitCode = int(options.watchExitCode)

    return options.compileType, options.dir, options.output, \
            options.resetBool, options.startRepo, options.endRepo, options.archi, \
            options.tracingjitBool, options.methodjitBool, options.watchExitCode, \
            options.valgSupport

def hgId(rev):
    return captureStdout(hgPrefix + ["id", "-n", "-r", rev])

def earliestKnownWorkingRev(tracingjitBool, methodjitBool, archNum):
    """Returns the oldest version of the shell that can run jsfunfuzz."""
    # Unfortunately, there are also interspersed runs of brokenness, such as:
    # * 0c8d4f846be8:bfb330182145 (~28226:28450).
    # * dd0b2f4d5299:??? (perhaps 64-bit only)
    # We don't deal with those at all, and --skip does not get out of such messes quickly.

    if methodjitBool:
        return "547af2626088" # ~52268, first rev that can run jsfunfuzz-n.js with -m
    else:
        return "8c52a9486c8f" # ~21110, switch from Makefile.ref to autoconf

def checkNumOfTests(str):
    # Sample bisect range message:
    # "Testing changeset 41831:4f4c01fb42c3 (2 changesets remaining, ~1 tests)"
    # This function looks for the number just after the "~".
    testNum = 0
    i = 0
    while i < len(str):
        if (str[i] == '~'):
            # This works no matter it is a one-digit or two-digit number.
            testNum = int(str[i+1] + str[i+2])
            # Sometimes estimation is not entirely accurate, one more test
            # round may be needed.
            # It will be checked to stop when the First bad changeset is found.
            testNum = testNum + 1;
            break
        i = i + 1
    if testNum == 0:
        raise Exception('The number of tests to be executed should not be 0.')
    return testNum

def extractChangesetFromBisectMessage(str):
    # "Testing changeset 41831:4f4c01fb42c3 (2 changesets remaining, ~1 tests)"
    r = re.compile(r"Testing changeset (\d+):(\w{12}) .*")
    m = r.match(str)
    return int(m.group(1))

def makeShell(shellCacheDir, sourceDir, archNum, compileType, tracingjitBool, methodjitBool, valgrindSupport, currRev):
    tempDir = tempfile.mkdtemp(prefix="abc")
    compilePath = os.path.join(tempDir, "compilePath")

    if verbose:
        print "Compiling in " + tempDir

    # Copy the js tree.
    cpJsTreeOrPymakeDir(sourceDir, 'js', compilePath)

    # Run autoconf.
    autoconfRun(compilePath)

    # Create objdir within the compilePath.
    objdir = os.path.join(compilePath, compileType + '-objdir')
    os.mkdir(objdir)

    # Run configure.
    threadsafe = False  # Let's disable support for threadsafety in the js shell
    macver = osCheck()
    cfgJsBin(archNum, compileType,
                      tracingjitBool, methodjitBool, valgrindSupport,
                      threadsafe, macver, os.path.join(compilePath, 'configure'), objdir)

    # Compile and copy the first binary.
    # Don't use pymake because older changesets may fail to compile.
    shell = compileCopy(archNum, compileType, str(currRev), False, shellCacheDir, objdir)
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

def bisectLabel(hgLabel, currRev, startRepo, endRepo):
    '''Tell hg what we learned about the revision.'''
    assert hgLabel in ("good", "bad", "skip")

    outputResult = captureStdout(hgPrefix + ['bisect', '-U', '--' + hgLabel, str(currRev)])
    if 'revision is:' in outputResult:
        print '\nautoBisect shows this is probably related to the following changeset:\n'
        print outputResult
        return None, startRepo, endRepo

    if verbose:
        # e.g. "Testing changeset 52121:573c5fa45cc4 (440 changesets remaining, ~8 tests)"
        print firstLine(outputResult)

    currRev = extractChangesetFromBisectMessage(firstLine(outputResult))
    assert currRev is not None

    # Update the startRepo/endRepo values.
    start = startRepo
    end = endRepo
    if hgLabel == 'bad':
        end = int(currRev)
    elif hgLabel == 'good':
        start = int(currRev)
    elif hgLabel == 'skip':
        pass

    return currRev, start, end

def firstLine(s):
    return s.split('\n')[0]

# This function removes a directory along with its subdirectories.
def rmDirInclSubDirs(dir):
    #print 'Removing ' + dir
    shutil.rmtree(dir)

if __name__ == '__main__':
    main()

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

import os, shutil, subprocess, sys
from optparse import OptionParser

path0 = os.path.dirname(sys.argv[0])
path2 = os.path.abspath(os.path.join(path0, "..", "jsfunfuzz"))
sys.path.append(path2)
from fnStartjsfunfuzz import *

def main():
    # Do not support Windows XP because the ~ folder is in "/Documents and Settings/",
    # which contains spaces. This breaks MinGW, which is what MozillaBuild uses.
    # From Windows Vista onwards, the folder is in "/Users/".
    # Edit 2: Don't support Windows till XP is deprecated, and when we create fuzzing
    # directories in ~-land instead of in /c/. We lack permissions when we move from
    # /c/ to ~-land in Vista/7.
    if os.name == 'nt':
        raise Exception('autoBisect is not supported on Windows.')
    verbose = True

    # Parse options and parameters from the command-line.
    filename = sys.argv[-1:][0]
    options = parseOpts()
    (compileType, sourceDir, stdoutOutput, resetBool, startRepo, endRepo, \
     archNum, tracingjitBool, methodjitBool, watchExitCode, valgrindSupport) = options

    os.chdir(sourceDir)

    # Refresh source directory (overwrite all local changes) to default tip if required.
    if resetBool:
        subprocess.call(['hg', 'up', '-C', 'default'])

    # Specify `hg bisect` ranges.
    subprocess.call(['hg', 'bisect', '-r'])
    # If in "bug" mode, this startRepo changeset does not exhibit the issue.
    subprocess.call(['hg', 'bisect', '-g', str(startRepo)])
    # If in "bug" mode, this endRepo changeset exhibits the issue.
    stdoutNumOfTests = captureStdout(['hg', 'bisect', '-b', str(endRepo)])
    print stdoutNumOfTests

    # Find out the number of tests to be executed based on the initial hg bisect output.
    numOfTests = checkNumOfTests(stdoutNumOfTests)

    # For main directory, change into Desktop directory.
    mainDir = os.path.expanduser('~/Desktop/')

    for i in xrange(numOfTests):
        # Change into main directory.
        os.chdir(mainDir)

        autoBisectPath = 'autoBisect-' + compileType + '-' + archNum + '-s' + \
                         str(startRepo) + '-e' + str(endRepo)

        # Create the autoBisect folder.
        try:
            os.makedirs(autoBisectPath)
        except OSError:
            raise Exception('The autoBisect path at "' + autoBisectPath + '" already exists!')

        # Change into autoBisectPath.
        os.chdir(autoBisectPath)

        # Copy the js tree to the autoBisect path.
        # Don't use pymake because older changesets may fail to compile.
        cpJsTreeOrPymakeDir(os.path.expanduser(sourceDir), 'js')
        os.chdir('compilePath')  # Change into compilation directory.

        autoconfRun()

        # Create objdirs within the compilePaths.
        os.mkdir(compileType + '-objdir')
        os.chdir(compileType + '-objdir')

        # Compile the first binary.
        branchType = 'autoBisectBranch'
        if 'jaegermonkey' in sourceDir:
            branchType = 'jm'

        # Configure the js binary.
        threadsafe = False  # Let's disable support for threadsafety in the js shell
        macver = osCheck()
        cfgJsBin(archNum, compileType, branchType,
                          tracingjitBool, methodjitBool, valgrindSupport,
                          threadsafe, macver)

        if 'jaegermonkey' in sourceDir:
            branchType = 'autoBisectBranch'  # Reset the branchType

        # Compile and copy the first binary.
        try:
            jsShellName = compileCopy(archNum, compileType, branchType, False)
        except:
            print 'The current "good" repository that should be double-checked:', str(startRepo)
            print 'The current "bad" repository that should be double-checked:', str(endRepo)
            # Consider implementing `hg bisect --skip`. Exit code 1 should also be skipped.
            raise Exception('Compilation failed.')

        # In Windows, executables end in .exe...
        if os.name == 'nt':
            jsShellName = jsShellName + '.exe'

        # Check that the js shell actually exists.
        try:
            os.path.isfile(jsShellName)
        except:
            raise Exception(jsShellName + ' doesn\'t exist!')

        # Change back into compilePath.
        os.chdir('../')

        # Test compilePath.
        if verbose:
            print 'DEBUG - This should be the compilePath:'
            print 'DEBUG - %s\n' % os.getcwdu()
            if 'compilePath' not in os.getcwdu():
                raise Exception('We are not in compilePath.')

        os.chdir('../')  # Change into autoBisectPath directory.
        autoBisectFullPath = os.path.expanduser(os.getcwdu())

        # This is only needed if testcase is altered to add the quit() function,
        # in the interactive shell testing located in the testBinary function.
        # Even if the problem at the interactive shell testing is fixed, there
        # apparently is still a bug here... :(
        #if i == 0:
        #    shutil.copyfile(filename, 'testcase.js')
        #    filename = 'testcase.js'

        (stdoutStderr, exitCode) = testBinary(jsShellName, filename, methodjitBool,
                                              tracingjitBool, valgrindSupport)

        # Switch to hg repository directory.
        os.chdir(os.path.expanduser(sourceDir))

        if (stdoutStderr.find(stdoutOutput) != -1) and (stdoutOutput != ''):
            (result, startRepo, endRepo) = bisectLabel('bad', startRepo, endRepo)

            # Label a changeset "bad" if required Valgrind output is found.
            if (valgrindSupport == True):
                print 'Required Valgrind output was seen.'
            # Label the changeset "bad" if the exact assert is found (only in debug shells)
            if (compileType == 'dbg') and (exitCode != 0):
                print 'Required assertion message was seen.'

            rmDirInclSubDirs(autoBisectFullPath)
            # Break out of for loop if the required revision changeset is found.
            if 'revision is:' in result:
                break

        # Label the changeset "bad" if the exit code is negative, between 129 to 159
        # (SIGBUS, SIGSEGV etc.) or if the watched exit code is observed.
        elif (129 <= exitCode <= 159) or (exitCode == watchExitCode) or (exitCode < 0):
            (result, startRepo, endRepo) = bisectLabel('bad', startRepo, endRepo)

            rmDirInclSubDirs(autoBisectFullPath)
            # Break out of for loop if the required revision changeset is found.
            if 'revision is:' in result:
                break

        # "Good" changesets.
        elif exitCode != watchExitCode:
            if (exitCode == 0) or (3 <= exitCode <= 6):
                (result, startRepo, endRepo) = bisectLabel('good', startRepo, endRepo)

                rmDirInclSubDirs(autoBisectFullPath)
                # Break out of for loop if the required revision changeset is found.
                if 'revision is:' in result:
                    break

        else:
            raise Exception('Unknown exit code hit:', exitCode)

    # Reset `hg bisect` after finishing everything.
    subprocess.call(['hg', 'bisect', '-r'])

def parseOpts():
    usage = 'Usage: %prog [options] filename'
    parser = OptionParser(usage)
    # See http://docs.python.org/library/optparse.html#optparse.OptionParser.disable_interspersed_args
    parser.disable_interspersed_args()

    # autoBisect details
    parser.add_option('-c', '--compileType',
                      dest='compileType',
                      type='choice',
                      choices=['dbg', 'opt'],
                      default='dbg',
                      help='js shell compile type. Defaults to "dbg"')
    parser.add_option('-d', '--dir',
                      dest='dir',
                      default=os.path.expanduser('~/tracemonkey/'),
                      help='Source code directory. Defaults to "~/tracemonkey/"')
    parser.add_option('-o', '--output',
                      dest='output',
                      default='',
                      help='Stdout or stderr output to be observed. Defaults to "". ' + \
                           'For assertions, set to "ssertion fail"')
    parser.add_option('-r', '--resetToTipFirstBool',
                      dest='resetBool',
                      action='store_true',
                      default=False,
                      help='First reset to default tip overwriting all local changes. ' + \
                           'Equivalent to first executing `hg update -C default`. ' + \
                           'Defaults to "False"')

    # Define the start and end repositories.
    parser.add_option('-s', '--start',
                      dest='startRepo',
                      help='Start repository (earlier). Set to "tip" here, and ' + \
                           'id where the symptom first exhibits at -e instead, ' + \
                           'if the patch that fixed an issue is desired.')
    parser.add_option('-e', '--end',
                      dest='endRepo',
                      default='tip',
                      help='End repository (later). Defaults to "tip"')

    # Define the architecture to be tested.
    parser.add_option('-a', '--architecture',
                      dest='archi',
                      type='choice',
                      choices=['32', '64'],
                      help='Test architecture. Only accepts "32" or "64"')

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

    # Special case in which a specific exit code needs to be observed.
    parser.add_option('-w', '--watchExitCode',
                      dest='watchExitCode',
                      type='choice',
                      choices=['3', '4', '5', '6'],
                      help='Look out for a specific exit code in the range [3,6]')

    (options, args) = parser.parse_args()

    # Only WinXP/Vista/7, Linux and Mac OS X 10.6.x are supported. This is what
    # the osCheck() function checks. Though, Windows platforms are already unsupported.
    osCheck()
    # Check for a correct number of arguments.
    if len(args) != 1:
        parser.error('There is a wrong number of arguments.')

    # A startRepo value must be input.
    if options.startRepo == None:
        parser.error('Please specify an earlier start repository for the bisect range.')

    # Turn some parameters into integers.
    #options.archi = int(options.archi)  # archNum should remain as a string due to historical reasons.
    options.startRepo = int(options.startRepo)
    if options.endRepo != 'tip':
        options.endRepo = int(options.endRepo)
    if options.watchExitCode:
        options.watchExitCode = int(options.watchExitCode)

    # Only support Valgrind on Linux for the moment, since Valgrind doesn't yet
    # work on Mac OS X 10.6.x.
    if (os.uname()[0] != 'Linux') and (options.valgSupport == True):
        parser.error('Valgrind is only supported on Linux.')

    # 32-bit js shells have only been tested to compile successfully from number 21500.
    if (options.archi == '32') and (options.startRepo < 21500) and \
        (options.dir == os.path.expanduser('~/tracemonkey/')):
        parser.error('The changeset number for 32-bit default TM must ' + \
                     'at least be 21500, which corresponds to TM changeset 04c360f123e5.')
    # 64-bit js shells have only been tested to compile successfully from
    # number 21715 on Ubuntu Linux 10.04 LTS.
    if (options.archi == '64') and (options.startRepo < 21500) and \
        (options.dir == os.path.expanduser('~/tracemonkey/')):
        if (options.startRepo < 1500) or \
            ((1500 <= options.startRepo < 21500) and (options.endRepo != 'tip')):
            parser.error('The changeset number for 64-bit default TM must ' + \
                         'at least be 1500, which corresponds to TM changeset ' + \
                         '28dac0d48126. (Only applicable to tip as endRepo, ' + \
                         'else 21500 is the startRepo limit.)')


    return options.compileType, options.dir, options.output, \
            options.resetBool, options.startRepo, options.endRepo, options.archi, \
            options.tracingjitBool, options.methodjitBool, options.watchExitCode, \
            options.valgSupport

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

# Run the testcase on the compiled js binary.
def testBinary(shell, file, methodjitBool, tracingjitBool, valgSupport):
    methodJit = ['-m'] if methodjitBool else []
    tracingJit = ['-j'] if tracingjitBool else []
    testBinaryCmd = ['./' + shell] + methodJit + tracingJit + [file]
    if valgSupport:
        testBinaryCmd = ['valgrind'] + testBinaryCmd
    print 'The testing command is:', ' '.join(testBinaryCmd)

    # Capture stdout and stderr into the same string.
    p = subprocess.Popen(testBinaryCmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    retCode = p.returncode
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
    #    testBinaryCmd3 = subprocess.Popen(['./' + shell, methodJit, tracingJit, '-i'],
    #        stdin=(subprocess.Popen(['cat', file])).stdout)
    #    output2 = testBinaryCmd3.communicate()[0]
    #    retCode = testBinaryCmd3.returncode
    #    print 'The exit code is:', retCode
    #    print 'The second output is:', output2
    return out + "\n" + err, retCode

# This function labels a changeset as "good" or "bad" depending on parameters.
def bisectLabel(gdBad, startRepo, endRepo):
    bisectLabelTuple = ()
    if gdBad == 'bad':
        bisectLabelTuple = ('BAD', '-b')
    elif gdBad == 'good':
        bisectLabelTuple = ('GOOD', '-g')

    print bisectLabelTuple[0], 'changeset: hg bisect', bisectLabelTuple[1]
    outputResult = captureStdout(['hg', 'bisect', bisectLabelTuple[1]])
    if 'revision is:' in outputResult:
        print '\nautoBisect shows this is probably related to the following changeset:\n'
    print outputResult

    currRev = captureStdout(['hg', 'identify', '-n'])
    print 'autoBisect is now currently in hg revision:', currRev

    start = startRepo
    end = endRepo
    # Update the startRepo/endRepo values.
    if gdBad == 'bad':
        end = int(currRev)
    elif gdBad == 'good':
        start = int(currRev)
    return outputResult, start, end

# This function removes a directory along with its subdirectories.
def rmDirInclSubDirs(dir):
    print 'Now removing ' + dir + ', located at: ' + dir
    shutil.rmtree(dir)

if __name__ == '__main__':
    main()

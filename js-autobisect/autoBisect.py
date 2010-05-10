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

import os, subprocess, sys
from optparse import OptionParser

sys.path.append('../jsfunfuzz/')
from fnStartjsfunfuzz import *

def main():
    # Do not support Windows XP because the ~ folder is in "/Documents and Settings/",
    # which contains spaces. This breaks MinGW, which is what MozillaBuild uses.
    # From Windows Vista onwards, the folder is in "/Users/".
    if os.name == 'nt':
        if '5.1' in captureStdout('uname'):
            raise Exception('autoBisect is not supported on Windows XP.')
    verbose = True
    # Parse options and parameters from the command-line.
    filename = sys.argv[-1:][0]
    options = parseOpts()
    (bugOrWfm, compileType, sourceDir, stdoutOutput, resetBool, startRepo, endRepo, archNum, \
     tracingjitBool, methodjitBool, watchExitCode) = options

    os.chdir(sourceDir)

    # Refresh source directory (overwrite all local changes) to default tip if required.
    if resetBool:
        subprocess.call(['hg up -C default'], shell=True)

    # Reverse if a bisect range to find a WFM issue is specified.
    if bugOrWfm == 'wfm':
        tempVal = ''
        tempVal = startRepo
        startRepo = endRepo
        endRepo = tempVal

    # Specify `hg bisect` ranges.
    subprocess.call(['hg bisect -r'], shell=True)
    # If in "bug" mode, this startRepo changeset does not exhibit the issue.
    subprocess.call(['hg bisect -g ' + startRepo], shell=True)
    # If in "bug" mode, this endRepo changeset exhibits the issue.
    stdoutNumOfTests = captureStdout('hg bisect -b ' + endRepo)

    # Find out the number of tests to be executed based on the initial hg bisect output.
    numOfTests = checkNumOfTests(stdoutNumOfTests)

    # For main directory, change into Desktop directory.
    mainDir = os.path.expanduser('~/Desktop/')

    # Change into main directory.
    os.chdir(mainDir)

    numOfTests = 1  #DEBUG - delete this when finished testing.
    for i in xrange(numOfTests):
        autoBisectPath = 'autoBisect-' + compileType + '-' + archNum + '-s' + \
                         startRepo + '-e' + endRepo
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
        os.makedirs('compilePath')
        os.chdir('compilePath')  # Change into compilation directory.

        autoconfRun()

        # Create objdirs within the compilePaths.
        os.mkdir(compileType + '-objdir')
        os.chdir(compileType + '-objdir')

        # Compile the first binary.
        branchType = 'autoBisectBranch'
        if 'jaeger' in sourceDir:
            branchType = 'jm'
        valgrindSupport = False  # Let's disable support for valgrind in the js shell
        threadsafe = False  # Let's disable support for threadsafety in the js shell
        configureJsBinary(archNum, compileType, branchType, valgrindSupport, threadsafe)

        if 'jaeger' in sourceDir:
            branchType = 'autoBisectBranch'  # Reset the branchType
        # Compile and copy the first binary.
        jsShellName = compileCopy(archNum, compileType, branchType, False)
        # Change back into compilePath.
        os.chdir('../')

        # Test compilePath.
        if verbose:
            print 'DEBUG - This should be the compilePath:'
            print 'DEBUG - %s\n' % os.getcwdu()
            if 'compilePath' not in os.getcwdu():
                raise Exception('We are not in compilePath.')

        os.chdir('../../')  # Change into fuzzPath directory.

    # a js shell should be inside.
    # test using CLI argument.
# cat into interactive shell if passing as a CLI argument cannot reproduce the issue
# use stdoutOutput, tracingjitBool, methodjitBool, watchExitCode
# look out for the First bad
# remove directory
# break out
# if compilation fails, show the startRepo and endRepo names before quitting out of main. Place in except: ?

# remember to delete the manual numOfTests = 1

#for ((a=0; a <= LIMIT ; a++))  # Double parentheses, and "LIMIT" with no "$".
#do
#bash ~/Desktop/autoBisect.sh ~/Desktop/2interesting/563210.js dbg bug "ssertion fail" # REPLACEME
##bash ~/Desktop/autoBisect-jm-no-m-with-j.sh ~/Desktop/2interesting/w35-reduced.js dbg bug "ssertion failure"
##bash ~/Desktop/autoBisect.sh ~/Desktop/2interesting/563127.js opt bug "" # REPLACEME
##bash ~/Desktop/autoBisect-notExitCode.sh ~/Desktop/2interesting/543100.js opt bug "" # REPLACEME
#done


    # Reset `hg bisect` after finishing everything.
    subprocess.call(['hg bisect -r'], shell=True)

def parseOpts():

    usage = 'Usage: %prog [options] filename'
    parser = OptionParser(usage)
    # See http://docs.python.org/library/optparse.html#optparse.OptionParser.disable_interspersed_args
    parser.disable_interspersed_args()

    # autoBisect details
    parser.add_option('-b', '--bugOrWfm',
                      dest='bugOrWfm',
                      type='choice',
                      choices=['bug', 'wfm'],
                      default='bug',
                      help='Bisect to find a bug or WFM issue. ' + \
                           'Only accepts "bug" or "wfm". ' + \
                           'Defaults to "bug"')
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
                      help='Stdout or stderr output to be observed')
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
                      help='Start repository (earlier)')
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

    # Special case in which a specific exit code needs to be observed.
    parser.add_option('-w', '--watchExitCode',
                      dest='watchExitCode',
                      type='choice',
                      choices=['3', '4', '5', '6'],
                      help='Look out for a specific exit code in the range [3,6]')

    (options, args) = parser.parse_args()
    if len(args) != 1:
        parser.error('There is a wrong number of arguments.')
    if options.startRepo == None:
        parser.error('Please specify an earlier start repository for the bisect range.')
    return options.bugOrWfm, options.compileType, options.dir, options.output, \
            options.resetBool, options.startRepo, options.endRepo, options.archi, \
            options.tracingjitBool, options.methodjitBool, options.watchExitCode

def checkNumOfTests(str):
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


if __name__ == '__main__':
    main()

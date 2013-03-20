#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import with_statement

import os
import platform
import random
import shutil
import subprocess
import sys

from copy import deepcopy
from optparse import OptionParser
from tempfile import mkdtemp

from compileShell import CompiledShell, cfgJsCompileCopy, copyJsSrcDirs
from inspectShell import archOfBinary, testDbgOrOpt, verifyBinary
import buildOptions

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
from countCpus import cpuCount
from downloadBuild import downloadBuild, downloadLatestBuild, mozPlatform
from hgCmds import getRepoHashAndId, getRepoNameFromHgrc, patchHgRepoUsingMq
from lithOps import knownBugsDir
from subprocesses import captureStdout, dateStr, isLinux, isMac, isWin, normExpUserPath, shellify, \
    vdump

def machineTimeoutDefaults(options):
    '''Sets different defaults depending on the machine type or debugger used.'''
    # FIXME: Set defaults for Pandaboard ES w/ & w/o Valgrind.
    if options.buildOptions.runWithVg:
        return 300
    elif platform.uname()[1] == 'tegra-ubuntu':
        return 180
    elif platform.uname()[4] == 'armv7l':
        return 600
    else:
        return 10  # If no timeout preference is specified, use 10 seconds.

def parseOptions():
    usage = 'Usage: %prog [options]'
    parser = OptionParser(usage)

    parser.set_defaults(
        disableCompareJit = False,
        disableRndFlags = False,
        noStart = False,
        timeout = 0,
        buildOptions = ""
    )

    parser.add_option('--disable-comparejit', dest='disableCompareJit', action='store_true',
                      help='Disable comparejit fuzzing.')
    parser.add_option('--disable-random-flags', dest='disableRndFlags', action='store_true',
                      help='Disable random flag fuzzing.')
    parser.add_option('--nostart', dest='noStart', action='store_true',
                      help='Compile shells only, do not start fuzzing.')

    # Specify how the shell will be built.
    # See buildOptions.py for details.
    parser.add_option('-b', '--build',
                      dest='buildOptions',
                      help='Specify build options, e.g. -b "-c opt --arch=32" (python buildOptions.py --help)')

    parser.add_option('-t', '--timeout', type='int', dest='timeout',
                      help='Sets the timeout for loopjsfunfuzz.py. ' + \
                           'Defaults to taking into account the speed of the computer and ' + \
                           'debugger (if any).')

    parser.add_option('-p', '--set-patchDir', dest='patchDir',
                      #help='Define the path to a single patch or to a directory containing mq ' + \
                      #     'patches. Must have a "series" file present, containing the names ' + \
                      #     'of the patches, the first patch required at the bottom of the list.')
                      help='Define the path to a single patch. Multiple patches are not yet ' + \
                           'supported.')

    options, args = parser.parse_args()

    if options.patchDir:
        options.patchDir = normExpUserPath(options.patchDir)

    if not options.disableCompareJit:
        options.buildOptions += " --enable-more-deterministic"

    options.buildOptions = buildOptions.parseShellOptions(options.buildOptions)

    options.timeout = options.timeout or machineTimeoutDefaults(options)

    return options

def envDump(shell, log):
    '''Dumps environment to file.'''
    with open(log, 'ab') as f:
        f.write('Information about shell:\n\n')

        f.write('Create another shell in autobisect-cache like this one:\n')
        f.write(shellify(["python", "-u", os.path.join(path0, "compileShell.py"),
            "-R", shell.getRepoDir(), "-b", shell.buildOptions.inputArgs]) + "\n\n")

        f.write('Full environment is: ' + str(shell.getEnvFull()) + '\n')
        f.write('Environment variables added are:\n')
        f.write(shellify(shell.getEnvAdded()) + '\n\n')

        f.write('Configuration command was:\n')
        f.write(shellify(shell.getCfgCmdExclEnv()) + '\n\n')

        f.write('Full configuration command with needed environment variables is:\n')
        f.write(shellify(shell.getEnvAdded()) + ' ' + shellify(shell.getCfgCmdExclEnv()) + '\n\n')

def cmdDump(shell, cmdList, log):
    '''Dump commands to file.'''
    with open(log, 'ab') as f:
        f.write('Command to be run is:\n')
        f.write(shellify(cmdList) + '\n')
        f.write('========================================================\n')
        f.write('|  Fuzzing %s js shell builds\n' %
                     (shell.getRepoName() ))
        f.write('|  DATE: %s\n' % dateStr())
        f.write('========================================================\n\n')

def localCompileFuzzJsShell(options):
    '''Compiles and readies a js shell for fuzzing.'''
    print dateStr()
    localOrigHgHash, localOrigHgNum, isOnDefault = getRepoHashAndId(options.buildOptions.repoDir)

    # Assumes that all patches that need to be applied will be done through --enable-patch-dir=FOO.
    assert captureStdout(['hg', '-R', options.buildOptions.repoDir, 'qapp'])[0] == ''

    if options.patchDir:  # Note that only JS patches are supported, not NSPR.
        # Assume mq extension enabled. Series file should be optional if only one patch is needed.
        assert not os.path.isdir(options.patchDir), \
            'Support for multiple patches has not yet been added.'
        assert os.path.isfile(options.patchDir)
        p1name = patchHgRepoUsingMq(options.patchDir, options.buildOptions.repoDir)

    appendStr = ''
    if options.patchDir:
        appendStr += '-patched'
    fuzzResultsDirStart = 'c:\\' if platform.uname()[2] == 'XP' else \
        normExpUserPath(os.path.join('~', 'Desktop'))  # WinXP has spaces in the user directory.
    buildIdentifier = getRepoNameFromHgrc(options.buildOptions.repoDir) + '-' + localOrigHgNum + "-" + \
        localOrigHgHash
    fullPath = mkdtemp(appendStr + os.sep,
                       buildOptions.computeShellName(options.buildOptions, buildIdentifier) + "-",
                       fuzzResultsDirStart)
    vdump('Base temporary directory is: ' + fullPath)

    myShell = CompiledShell(options.buildOptions, localOrigHgHash, fullPath)

    # Copy js src dirs to compilePath, to have a backup of shell source in case repo gets updated.
    copyJsSrcDirs(myShell)

    if options.patchDir:
        # Remove the patches from the codebase if they were applied.
        assert not os.path.isdir(options.patchDir), \
            'Support for multiple patches has not yet been added.'
        assert p1name != ''
        if os.path.isfile(options.patchDir):
            subprocess.check_call(['hg', '-R', myShell.getRepoDir(), 'qpop'])
            vdump("First patch qpop'ed.")
            subprocess.check_call(['hg', '-R', myShell.getRepoDir(), 'qdelete', p1name])
            vdump("First patch qdelete'd.")

    # Ensure there is no applied patch remaining in the main repository.
    assert captureStdout(['hg', '-R', myShell.getRepoDir(), 'qapp'])[0] == ''

    # Compile the shell to be fuzzed and verify it.
    cfgJsCompileCopy(myShell, options.buildOptions)
    verifyBinary(myShell, options.buildOptions)

    analysisPath = os.path.abspath(os.path.join(path0, os.pardir, 'jsfunfuzz', 'analysis.py'))
    if os.path.exists(analysisPath):
        shutil.copy2(analysisPath, fullPath)

    # Construct a command-line for running loopjsfunfuzz.py
    cmdList = ['python', '-u']
    cmdList.append(normExpUserPath(os.path.join(path0, 'loopjsfunfuzz.py')))
    cmdList.append('--repo=' + myShell.getRepoDir())
    cmdList += ["--build", options.buildOptions.inputArgs]
    if options.buildOptions.runWithVg:
        cmdList.append('--valgrind')
    if not options.disableCompareJit:
        cmdList.append('--comparejit')
    if not options.disableRndFlags:
        cmdList.append('--random-flags')
    cmdList.append(str(options.timeout))
    cmdList.append(knownBugsDir(myShell.getRepoName()))
    cmdList.append(myShell.getShellBaseTempDirWithName())

    # Write log files describing configuration parameters used during compilation.
    localLog = normExpUserPath(os.path.join(myShell.getBaseTempDir(), 'log-localjsfunfuzz.txt'))
    envDump(myShell, localLog)
    cmdDump(myShell, cmdList, localLog)

    with open(localLog, 'rb') as f:
        for line in f:
            if 'Full environment is' not in line:
                print line,

    # FIXME: Randomize logic should be developed later, possibly together with target time in
    # loopjsfunfuzz.py. Randomize Valgrind runs too.

    return myShell, cmdList

def main():
    options = parseOptions()

    fuzzShell, cList = localCompileFuzzJsShell(options)
    startDir = fuzzShell.getBaseTempDir()

    if options.noStart:
        print 'Exiting, --nostart is set.'
        sys.exit(0)
    else:
        assert os.path.exists('jsfunfuzz.js'),
            'jsfunfuzz.js should be in the same location for the fuzzing harness to work.'

    # Commands to simulate bash's `tee`.
    tee = subprocess.Popen(['tee', 'log-jsfunfuzz.txt'], stdin=subprocess.PIPE, cwd=startDir)

    # Start fuzzing the newly compiled builds.
    subprocess.call(cList, stdout=tee.stdin, cwd=startDir)


# Run main when run as a script, this line means it will not be run as a module.
if __name__ == '__main__':
    main()

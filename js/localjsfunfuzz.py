#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import with_statement

import os
import platform
import shutil
import subprocess
import sys

from copy import deepcopy
from optparse import OptionParser
from tempfile import mkdtemp

from compileShell import CompiledShell, cfgCompileCopy, copyJsSrcDirs
from inspectShell import archOfBinary, testDbgOrOpt, verifyBinary

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
from downloadBuild import downloadBuild, downloadLatestBuild, mozPlatform
from hgCmds import getMcRepoDir, getRepoHashAndId, patchHgRepoUsingMq
from lithOps import knownBugsDir
from subprocesses import captureStdout, dateStr, isLinux, isMac, isWin, normExpUserPath, shellify, \
    vdump

def machineTimeoutDefaults(options):
    '''Sets different defaults depending on the machine type or debugger used.'''
    # FIXME: Set defaults for Pandaboard ES w/ & w/o Valgrind.
    if options.testWithVg:
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
        compileType = 'dbg,opt',
        repoDir = getMcRepoDir()[1],
        timeout = 0,
        isThreadsafe = False,
        buildWithAsan = False,
        llvmRootSrcDir = normExpUserPath('~/llvm'),
        enableMoreDeterministic = False,
        enableRootAnalysis = False,
        testWithVg = False,
    )

    parser.add_option('--disable-comparejit', dest='disableCompareJit', action='store_true',
                      help='Disable comparejit fuzzing.')
    parser.add_option('--disable-random-flags', dest='disableRndFlags', action='store_true',
                      help='Disable random flag fuzzing.')
    parser.add_option('--nostart', dest='noStart', action='store_true',
                      help='Compile shells only, do not start fuzzing.')

    parser.add_option('-a', '--arch', dest='arch', type='choice', choices=('32', '64'),
                      help='Sets the shell architecture to be fuzzed. Can only be "32" or "64".')
    parser.add_option('-c', '--compileType', dest='compileType',
                      # FIXME: This should be improved. Seems like a hackish way.
                      help='Sets the shell type to be fuzzed. Defaults to "dbg". Note that both ' + \
                           'debug and opt will be compiled by default for easy future testing.')
    parser.add_option('-R', '--repoDir', dest='repoDir',
                      help='Sets the source repository. Defaults to "%default".')
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

    parser.add_option('--build-with-asan', dest='buildWithAsan', action='store_true',
                      help='Fuzz builds with AddressSanitizer support. Defaults to "%default".')
    parser.add_option('--llvm-root', dest='llvmRootSrcDir',
                      help='Specify the LLVM root source dir. Defaults to "%default".')
    parser.add_option('--enable-more-deterministic', dest='enableMoreDeterministic',
                      action='store_true',
                      help='Build shells with --enable-more-deterministic. ' + \
                           'Defaults to True if compareJIT fuzzing is enabled. ' + \
                           'Otherwise, defaults to "%default".')
    parser.add_option('--enable-root-analysis', dest='enableRootAnalysis', action='store_true',
                      help='Enable root analysis support. Defaults to "%default".')
    parser.add_option('--enable-threadsafe', dest='isThreadsafe', action='store_true',
                      help='Enable compilation and fuzzing of threadsafe js shell. ' + \
                           'NSPR should first be installed, see: ' + \
                           'https://developer.mozilla.org/en/NSPR_build_instructions ' + \
                           'Defaults to "%default".')
    parser.add_option('--test-with-valgrind', dest='testWithVg', action='store_true',
                      help='Fuzz with valgrind. ' + \
                           'compareJIT will then be disabled due to speed issues. ' + \
                           'Defaults to "%default".')
    parser.add_option('-u', '--enable-tinderboxShell', action='store_true', dest='useTinderShell',
                      help='Use tinderbox js shells instead of compiling your own. ' + \
                           'Defaults to %default.')

    options, args = parser.parse_args()

    options.repoDir = normExpUserPath(options.repoDir)
    if options.patchDir:
        options.patchDir = normExpUserPath(options.patchDir)

    if isWin:
        assert ('x64' in os.environ['MOZ_TOOLS'].split(os.sep)[-1]) == (options.arch == '64')
    assert 'dbg' in options.compileType or 'opt' in options.compileType

    assert not (options.testWithVg and options.buildWithAsan)

    options.timeout = options.timeout or machineTimeoutDefaults(options.testWithVg)

    if not options.disableCompareJit:
        options.enableMoreDeterministic = True

    return options

class DownloadedJsShell:
    def __init__(self, options):
        if options.compileType == 'dbg,opt' or options.compileType == 'dbg':
            self.cType = 'dbg'  # 'dbg,opt' is the default setting for options.compileType
            if 'dbg' in options.compileType:
                print 'Setting to debug only even though opt is specified by default. ' + \
                      'Overwrite this by specifying the shell type explicitly.'
        elif options.compileType == 'opt':
            self.cType = 'opt'

        if options.arch == '32':
            self.pArchNum = '32'
            if isMac:
                self.pArchName = 'macosx'
            elif isLinux:
                self.pArchName = 'linux'
            elif isWin:
                self.pArchName = 'win32'
        elif options.arch == '64':
            self.pArchNum = '64'
            if isMac:
                self.pArchName = 'macosx64'
            elif isLinux:
                self.pArchName = 'linux64'
            elif isWin:
                raise Exception('Windows 64-bit builds are not supported yet.')
        else:
            raise Exception('Only either one of these architectures can be specified: 32 or 64')
        self.repoDir = options.repoDir
        self.repo = self.options.repoDir.split('/')[-1]
        self.shellVer = options.useTinderShell
    def mkFuzzDir(self, startDir):
        path = mkdtemp('', os.path.join('tinderjsfunfuzz-'), startDir)
        assert os.path.exists(path)
        return path
    def downloadShell(self, sDir):
        remoteTinderJsUrlStart = 'https://ftp.mozilla.org/pub/mozilla.org/firefox/tinderbox-builds/'
        # Revert filter change here, we're not sure what's going on, but this code should not be hit
        # anyway, needs a rewrite.
        tinderJsType = filter(None, self.repo) + '-' + self.pArchName + \
            '-debug' if 'dbg' in self.cType else ''
        if self.shellVer == 'latest':
            downloadLatestBuild(tinderJsType, getJsShell=True, workingDir=sDir)
        elif remoteTinderJsUrlStart in self.shellVer:
            downloadBuild(self.shellVer, cwd=sDir, jsShell=True, wantSymbols=False)
        else:
            raise Exception('Please specify either "latest" or ' + \
                            'the URL of the tinderbox build to be used.' + \
                            'e.g. FIXME')
        self.shellName = os.path.abspath(normExpUserPath(os.path.join(sDir, 'build', 'dist', 'js')))
        assert os.path.exists(self.shellName)

def envDump(shell, log):
    '''Dumps environment to file.'''
    with open(log, 'ab') as f:
        f.write('Information about ' + shell.getArch() + '-bit ' + shell.getCompileType() + \
                ' shell:\n\n')
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
        f.write('|  Fuzzing %s %s %s js shell builds\n' %
                     (shell.getArch() + '-bit', shell.getCompileType(), shell.getRepoName() ))
        f.write('|  DATE: %s\n' % dateStr())
        f.write('========================================================\n\n')

def localCompileFuzzJsShell(options):
    '''Compiles and readies a js shell for fuzzing.'''
    print dateStr()
    myShell = CompiledShell()
    myShell.setRepoDir(options.repoDir)
    localOrigHgHash, localOrigHgNum, isOnDefault = getRepoHashAndId(myShell.getRepoDir())
    myShell.setHgHash(localOrigHgHash)
    myShell.setHgNum(localOrigHgNum)

    # Assumes that all patches that need to be applied will be done through --enable-patch-dir=FOO.
    assert captureStdout(['hg', '-R', myShell.getRepoDir(), 'qapp'])[0] == ''

    if options.patchDir:  # Note that only JS patches are supported, not NSPR.
        # Assume mq extension enabled. Series file should be optional if only one patch is needed.
        assert not os.path.isdir(options.patchDir), \
            'Support for multiple patches has not yet been added.'
        assert os.path.isfile(options.patchDir)
        p1name = patchHgRepoUsingMq(options.patchDir, myShell.getRepoDir())

    myShell.setArch('64' if '64' in mozPlatform(options.arch) else '32')
    myOtherShell = deepcopy(myShell)
    # Default to compiling debug first.
    if 'dbg' in options.compileType:
        myShell.setCompileType('dbg')
        myOtherShell.setCompileType('opt')
    else:
        myShell.setCompileType('opt')
        myOtherShell.setCompileType('dbg')

    appendStr = ''
    if options.patchDir:
        appendStr += '-patched'
    fuzzResultsDirStart = 'c:\\' if platform.uname()[2] == 'XP' else \
        normExpUserPath(os.path.join('~', 'Desktop'))  # WinXP has spaces in the user directory.
    # FIXME: Remove myShell.getCompileType() once we randomly fuzz between the two at the same time.
    fullPath = mkdtemp(appendStr + os.sep, os.path.join(
        'jsfunfuzz-' + myShell.getCompileType() + '-' + myShell.getArch() + '-' + \
        myShell.getRepoName() + '-' + myShell.getHgNum() + '-' + \
        myShell.getHgHash() + '-'), fuzzResultsDirStart)
    myShell.setBaseTempDir(fullPath)
    myOtherShell.setBaseTempDir(fullPath)
    assert os.path.exists(myShell.getBaseTempDir())
    assert os.path.exists(myOtherShell.getBaseTempDir())
    vdump('Base temporary directory is: ' + myShell.getBaseTempDir())

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
    cfgCompileCopy(myShell, options)
    verifyBinary(myShell, options)

    # Compile the other shell for archival purposes and verify it.
    cfgCompileCopy(myOtherShell, options)
    verifyBinary(myOtherShell, options)

    analysisPath = os.path.abspath(os.path.join(path0, os.pardir, 'jsfunfuzz', 'analysis.py'))
    if os.path.exists(analysisPath):
        shutil.copy2(analysisPath, fullPath)

    # Construct the command to be run.
    cmdList = ['python', '-u']
    cmdList.append(normExpUserPath(os.path.join(path0, 'loopjsfunfuzz.py')))
    cmdList.append('--repo=' + myShell.getRepoDir())
    if options.testWithVg:
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
    envDump(myOtherShell, localLog)  # Also dump information about the other shell
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

    if options.useTinderShell is None:
        fuzzShell, cList = localCompileFuzzJsShell(options)
        startDir = fuzzShell.getBaseTempDir()
    else:
        assert False, 'Downloaded js shells do not yet work with the new APIs.'
        odjs = DownloadedJsShell(options)
        startDir = odjs.mkFuzzDir(CompiledShell().getBaseDir())
        odjs.downloadShell(startDir)

        analysisPath = os.path.abspath(os.path.join(path0, os.pardir, 'jsfunfuzz', 'analysis.py'))
        if os.path.exists(analysisPath):
            shutil.copy2(analysisPath, startDir)

        loopyTimeout = str(machineTimeoutDefaults(options.timeout))
        if options.testWithVg:
            # FIXME: Change this to whitelist Pandaboard ES board when we actually verify this.
            #if (isLinux or isMac) and platform.uname()[4] != 'armv7l':
            if isLinux or isMac:
                loopyTimeout = '300'
            else:
                raise Exception('Valgrind is only supported on Linux or Mac OS X machines.')

        lst = genJsCliFlagList(options)

        cList = genShellCmd(lst, loopyTimeout,
                            knownBugsDir(odjs.options.repoDir, odjs.repo), odjs.shellName, shFlagList)

        assert archOfBinary(odjs.shellName) == odjs.pArchNum  # 32-bit or 64-bit verification test.
        assert testDbgOrOpt(odjs.shellName) == odjs.cType

        localLog = normExpUserPath(os.path.join(startDir, 'log-localjsfunfuzz.txt'))
        with open(localLog, 'wb') as f:
            f.writelines('Command to be run is:\n')
            f.writelines(shellify(cList) + '\n')
            f.writelines('========================================================\n')
            f.writelines('|  Fuzzing %s %s %s js shell builds\n' % (odjs.pArchNum + '-bit',
                                                                    odjs.cType, odjs.repo ))
            f.writelines('|  DATE: %s\n' % dateStr())
            f.writelines('========================================================\n')

        with open(localLog, 'rb') as f:
            for line in f:
                print line,

    if options.noStart:
        print 'Exiting, --nostart is set.'
        sys.exit(0)

    # Commands to simulate bash's `tee`.
    tee = subprocess.Popen(['tee', 'log-jsfunfuzz.txt'], stdin=subprocess.PIPE, cwd=startDir)

    # Start fuzzing the newly compiled builds.
    subprocess.call(cList, stdout=tee.stdin, cwd=startDir)


# Run main when run as a script, this line means it will not be run as a module.
if __name__ == '__main__':
    main()

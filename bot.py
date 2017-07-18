#!/usr/bin/env python
# coding=utf-8
# pylint: disable=broad-except,fixme,import-error,invalid-name,line-too-long,missing-docstring,no-else-return,too-few-public-methods,too-many-arguments,wrong-import-position
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# bot.py ensures a build is available, then forks a bunch of fuzz-reduce processes

from __future__ import absolute_import, print_function

import multiprocessing
import os
import platform
import shutil
import sys
import tempfile

from optparse import OptionParser  # pylint: disable=deprecated-module

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, 'util'))
sys.path.insert(0, path1)
import downloadBuild
import hgCmds
import subprocesses as sps
import forkJoin
import createCollector
from LockDir import LockDir
path3 = os.path.abspath(os.path.join(path0, 'js'))
sys.path.append(path3)
import buildOptions
import compileShell
import loopjsfunfuzz

JS_SHELL_DEFAULT_TIMEOUT = 24  # see comments in loopjsfunfuzz.py for tradeoffs


class BuildInfo(object):
    """Store information related to the build, such as its directory, source and type."""

    def __init__(self, bDir, bType, bSrc, bRev, manyTimedRunArgs):
        self.buildDir = bDir
        self.buildType = bType
        self.buildSrc = bSrc
        self.buildRev = bRev
        self.mtrArgs = manyTimedRunArgs


def parseOpts():
    parser = OptionParser()
    parser.set_defaults(
        repoName='mozilla-central',
        targetTime=15 * 60,       # 15 minutes
        existingBuildDir=None,
        timeout=0,
        buildOptions=None,
        useTreeherderBuilds=False,
    )

    parser.add_option('-t', '--test-type', dest='testType', choices=['js', 'dom'],
                      help='Test type: "js" or "dom"')

    parser.add_option("--build", dest="existingBuildDir",
                      help="Use an existing build directory.")

    parser.add_option('--repotype', dest='repoName',
                      help='Sets the repository to be fuzzed. Defaults to "%default".')

    parser.add_option("--target-time", dest="targetTime", type='int',
                      help="Nominal amount of time to run, in seconds")

    parser.add_option('-T', '--use-treeherder-builds', dest='useTreeherderBuilds', action='store_true',
                      help='Download builds from treeherder instead of compiling our own.')

    # Specify how the shell will be built.
    # See js/buildOptions.py for details.
    parser.add_option('-b', '--build-options',
                      dest='buildOptions',
                      help='Specify build options, e.g. -b "-c opt --arch=32" for js (python buildOptions.py --help)')

    parser.add_option('--timeout', type='int', dest='timeout',
                      help="Sets the timeout for loopjsfunfuzz.py. "
                           "Defaults to taking into account the speed of the computer and debugger (if any).")

    options, args = parser.parse_args()
    if args:
        print("Warning: bot.py does not use positional arguments")

    if not options.testType or options.testType == 'dom':
        raise Exception('options.testType should be set to "js" now that only js engine fuzzing is supported')

    if not options.useTreeherderBuilds and not os.path.isdir(buildOptions.DEFAULT_TREES_LOCATION):
        # We don't have trees, so we must use treeherder builds.
        options.useTreeherderBuilds = True
        print("Trees were absent from default location: %s" % buildOptions.DEFAULT_TREES_LOCATION)
        print("Using treeherder builds instead...")

    if options.buildOptions is None:
        options.buildOptions = ''
    if options.useTreeherderBuilds and options.buildOptions != '':
        raise Exception('Do not use treeherder builds if one specifies build parameters')

    return options


def main():
    printMachineInfo()

    options = parseOpts()

    collector = createCollector.createCollector("jsfunfuzz")
    refreshSignatures(collector)

    options.tempDir = tempfile.mkdtemp("fuzzbot")
    print(options.tempDir)

    buildInfo = ensureBuild(options)
    assert os.path.isdir(buildInfo.buildDir)

    numProcesses = multiprocessing.cpu_count()
    if "-asan" in buildInfo.buildDir:
        # This should really be based on the amount of RAM available, but I don't know how to compute that in Python.
        # I could guess 1 GB RAM per core, but that wanders into sketchyville.
        numProcesses = max(numProcesses // 2, 1)
    if sps.isARMv7l:
        # Even though ARM boards generally now have many cores, each core is not as powerful
        # as x86/64 ones, so restrict fuzzing to only 1 core for now.
        numProcesses = 1

    forkJoin.forkJoin(options.tempDir, numProcesses, loopFuzzingAndReduction, options, buildInfo, collector)

    shutil.rmtree(options.tempDir)


def printMachineInfo():
    # Log information about the machine.
    print("Platform details: %s" % " ".join(platform.uname()))
    print("hg version: %s" % sps.captureStdout(['hg', '-q', 'version'])[0])

    # In here temporarily to see if mock Linux slaves on TBPL have gdb installed
    try:
        print("gdb version: %s" % sps.captureStdout(['gdb', '--version'], combineStderr=True,
                                                    ignoreStderr=True, ignoreExitCode=True)[0])
    except (KeyboardInterrupt, Exception) as e:
        print("Error involving gdb is: %r" % (e,))

    # FIXME: Should have if os.path.exists(path to git) or something
    # print "git version: " + sps.captureStdout(['git', 'version'], combineStderr=True, ignoreStderr=True, ignoreExitCode=True)[0]
    print("Python version: %s" % sys.version.split()[0])
    print("Number of cores visible to OS: %d" % multiprocessing.cpu_count())
    print("Free space (GB): %.2f" % sps.getFreeSpace("/", 3))

    hgrcLocation = os.path.join(path0, '.hg', 'hgrc')
    if os.path.isfile(hgrcLocation):
        print("The hgrc of this repository is:")
        with open(hgrcLocation, 'rb') as f:
            hgrcContentList = f.readlines()
        for line in hgrcContentList:
            print(line.rstrip())

    if os.name == 'posix':
        # resource library is only applicable to Linux or Mac platforms.
        import resource
        print("Corefile size (soft limit, hard limit) is: %r" % (resource.getrlimit(resource.RLIMIT_CORE),))


def refreshSignatures(collector):
    """Refresh signatures, copying from FuzzManager server to local sigcache."""
    # Btw, you should make sure the server generates the file using
    #     python manage.py export_signatures files/signatures.zip
    # occasionally, e.g. as a cron job.
    if collector.serverHost == "127.0.0.1":
        # The test server does not serve files
        collector.refreshFromZip(os.path.join(path0, "..", "FuzzManager", "server", "files", "signatures.zip"))
    else:
        # A production server will serve files
        collector.refresh()


def ensureBuild(options):
    if options.existingBuildDir:
        # Pre-downloaded treeherder builds (browser only for now)
        bDir = options.existingBuildDir
        bType = 'local-build'
        bSrc = bDir
        bRev = ''
        manyTimedRunArgs = []
    elif not options.useTreeherderBuilds:
        if options.testType == "js":
            # Compiled js shells
            options.buildOptions = buildOptions.parseShellOptions(options.buildOptions)
            options.timeout = options.timeout or machineTimeoutDefaults(options)

            with LockDir(compileShell.getLockDirPath(options.buildOptions.repoDir)):
                bRev = hgCmds.getRepoHashAndId(options.buildOptions.repoDir)[0]
                cshell = compileShell.CompiledShell(options.buildOptions, bRev)
                updateLatestTxt = (options.buildOptions.repoDir == 'mozilla-central')
                compileShell.obtainShell(cshell, updateLatestTxt=updateLatestTxt)

                bDir = cshell.getShellCacheDir()
                # Strip out first 3 chars or else the dir name in fuzzing jobs becomes:
                #   js-js-dbg-opt-64-dm-linux
                # This is because options.testType gets prepended along with a dash later.
                bType = buildOptions.computeShellType(options.buildOptions)[3:]
                bSrc = (
                    "Create another shell in shell-cache like this one:\n"
                    'python -u %s -b "%s -R %s" -r %s\n\n'
                    "==============================================\n"
                    "|  Fuzzing %s js shell builds\n"
                    "|  DATE: %s\n"
                    "==============================================\n\n" % (
                        os.path.join(path3, "compileShell.py"),
                        options.buildOptions.buildOptionsStr,
                        options.buildOptions.repoDir,
                        bRev,
                        cshell.getRepoName(),
                        sps.dateStr()
                    ))

                manyTimedRunArgs = mtrArgsCreation(options, cshell)
                print("buildDir is: %s" % bDir)
                print("buildSrc is: %s" % bSrc)
        else:
            # FIXME: We can probably remove the testType option
            raise Exception('Only testType "js" is supported.')
    else:
        # Treeherder js shells and browser
        # Download from Treeherder and call it 'build'
        # FIXME: Put 'build' somewhere nicer, like ~/fuzzbuilds/. Don't re-download a build that's up to date.
        # FIXME: randomize branch selection, get appropriate builds, use appropriate known dirs
        bDir = 'build'
        bType = downloadBuild.defaultBuildType(options.repoName, None, True)
        isJS = options.testType == 'js'
        bSrc = downloadBuild.downloadLatestBuild(bType, './', getJsShell=isJS, wantTests=not isJS)
        bRev = ''

        # These two lines are only used for treeherder js shells:
        shell = os.path.join(bDir, "dist", "js.exe" if sps.isWin else "js")
        manyTimedRunArgs = ["--random-flags", str(JS_SHELL_DEFAULT_TIMEOUT), "mozilla-central", shell]

    return BuildInfo(bDir, bType, bSrc, bRev, manyTimedRunArgs)


def loopFuzzingAndReduction(options, buildInfo, collector, i):
    tempDir = tempfile.mkdtemp("loop" + str(i))
    if options.testType == 'js':
        loopjsfunfuzz.many_timed_runs(options.targetTime, tempDir, buildInfo.mtrArgs, collector)
    else:
        raise Exception('Only js engine fuzzing is supported')


def machineTimeoutDefaults(options):
    """Set different defaults depending on the machine type or debugger used."""
    if options.buildOptions.runWithVg:
        return 300
    elif sps.isARMv7l:
        return 180
    else:
        return JS_SHELL_DEFAULT_TIMEOUT


def mtrArgsCreation(options, cshell):
    """Create many_timed_run arguments for compiled builds."""
    manyTimedRunArgs = []
    manyTimedRunArgs.append('--repo=' + sps.normExpUserPath(options.buildOptions.repoDir))
    manyTimedRunArgs.append("--build=" + options.buildOptions.buildOptionsStr)
    if options.buildOptions.runWithVg:
        manyTimedRunArgs.append('--valgrind')
    if options.buildOptions.enableMoreDeterministic:
        # Treeherder shells not using compareJIT:
        #   They are not built with --enable-more-deterministic - bug 751700
        manyTimedRunArgs.append('--comparejit')
    manyTimedRunArgs.append('--random-flags')

    # Ordering of elements in manyTimedRunArgs is important.
    manyTimedRunArgs.append(str(options.timeout))
    manyTimedRunArgs.append(cshell.getRepoName())  # known bugs' directory
    manyTimedRunArgs.append(cshell.getShellCacheFullPath())
    return manyTimedRunArgs


if __name__ == "__main__":
    main()

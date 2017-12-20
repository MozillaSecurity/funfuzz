# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Ensures a build is available, then forks a bunch of fuzz-reduce processes.

"""

from __future__ import absolute_import, print_function

import multiprocessing
import os
import platform
import shutil
import sys
import tempfile
import time

from optparse import OptionParser  # pylint: disable=deprecated-module

from .js import build_options
from .js import compile_shell
from .js import loop
from .util import download_build
from .util import hg_helpers
from .util import subprocesses as sps
from .util import fork_join
from .util import create_collector
from .util.lock_dir import LockDir

path0 = os.path.dirname(os.path.abspath(__file__))  # pylint: disable=invalid-name
path3 = os.path.abspath(os.path.join(path0, 'js'))  # pylint: disable=invalid-name
JS_SHELL_DEFAULT_TIMEOUT = 24  # see comments in loop for tradeoffs


class BuildInfo(object):  # pylint: disable=missing-param-doc,missing-type-doc,too-few-public-methods
    """Store information related to the build, such as its directory, source and type."""

    def __init__(self, bDir, bType, bSrc, bRev, manyTimedRunArgs):  # pylint: disable=too-many-arguments
        self.buildDir = bDir  # pylint: disable=invalid-name
        self.buildType = bType  # pylint: disable=invalid-name
        self.buildSrc = bSrc  # pylint: disable=invalid-name
        self.buildRev = bRev  # pylint: disable=invalid-name
        self.mtrArgs = manyTimedRunArgs  # pylint: disable=invalid-name


def parseOpts():  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    parser = OptionParser()
    parser.set_defaults(
        repoName='mozilla-central',
        targetTime=15 * 60,       # 15 minutes
        existingBuildDir=None,
        timeout=0,
        build_options=None,
        useTreeherderBuilds=False,
    )

    parser.add_option('-t', '--test-type', dest='testType', choices=['js'],
                      help='Test type: "js"', default='js')

    parser.add_option("--build", dest="existingBuildDir",
                      help="Use an existing build directory.")

    parser.add_option('--repotype', dest='repoName',
                      help='Sets the repository to be fuzzed. Defaults to "%default".')

    parser.add_option("--target-time", dest="targetTime", type='int',
                      help="Nominal amount of time to run, in seconds")

    parser.add_option('-T', '--use-treeherder-builds', dest='useTreeherderBuilds', action='store_true',
                      help='Download builds from treeherder instead of compiling our own.')

    # Specify how the shell will be built.
    parser.add_option('-b', '--build-options',
                      dest='build_options',
                      help='Specify build options, e.g. -b "-c opt --arch=32" for js '
                           '(python -m funfuzz.js.build_options --help)')

    parser.add_option('--timeout', type='int', dest='timeout',
                      help="Sets the timeout for loop. "
                           "Defaults to taking into account the speed of the computer and debugger (if any).")

    options, args = parser.parse_args()
    if args:
        print("Warning: bot does not use positional arguments")

    if not options.testType or options.testType == 'dom':
        raise Exception('options.testType should be set to "js" now that only js engine fuzzing is supported')

    if not options.useTreeherderBuilds and not os.path.isdir(build_options.DEFAULT_TREES_LOCATION):
        # We don't have trees, so we must use treeherder builds.
        options.useTreeherderBuilds = True
        print()
        print("Trees were absent from default location: %s" % build_options.DEFAULT_TREES_LOCATION)
        print("Using treeherder builds instead...")
        print()
        sys.exit("Fuzzing downloaded builds is disabled for now, until tooltool is removed. Exiting...")

    if options.build_options is None:
        options.build_options = ''
    if options.useTreeherderBuilds and options.build_options != '':
        raise Exception('Do not use treeherder builds if one specifies build parameters')

    return options


def main():  # pylint: disable=missing-docstring
    printMachineInfo()

    options = parseOpts()

    collector = create_collector.createCollector("jsfunfuzz")
    try:
        collector.refresh()
    except RuntimeError as ex:
        print()
        print("Unable to find required entries in .fuzzmanagerconf, exiting...")
        sys.exit(ex)

    options.tempDir = tempfile.mkdtemp("fuzzbot")
    print(options.tempDir)

    build_info = ensureBuild(options)
    assert os.path.isdir(build_info.buildDir)

    number_of_processes = multiprocessing.cpu_count()
    if "-asan" in build_info.buildDir:
        # This should really be based on the amount of RAM available, but I don't know how to compute that in Python.
        # I could guess 1 GB RAM per core, but that wanders into sketchyville.
        number_of_processes = max(number_of_processes // 2, 1)
    if sps.isARMv7l:
        # Even though ARM boards generally now have many cores, each core is not as powerful
        # as x86/64 ones, so restrict fuzzing to only 1 core for now.
        number_of_processes = 1

    fork_join.forkJoin(options.tempDir, number_of_processes, loopFuzzingAndReduction, options, build_info, collector)

    shutil.rmtree(options.tempDir)


def printMachineInfo():  # pylint: disable=invalid-name
    """Log information about the machine."""
    print("Platform details: %s" % " ".join(platform.uname()))
    print("hg version: %s" % sps.captureStdout(['hg', '-q', 'version'])[0])

    # In here temporarily to see if mock Linux slaves on TBPL have gdb installed
    try:
        print("gdb version: %s" % sps.captureStdout(['gdb', '--version'], combineStderr=True,
                                                    ignoreStderr=True, ignoreExitCode=True)[0])
    except (KeyboardInterrupt, Exception) as ex:  # pylint: disable=broad-except
        print("Error involving gdb is: %r" % (ex,))

    # FIXME: Should have if os.path.exists(path to git) or something  # pylint: disable=fixme
    # print("git version: %s" % sps.captureStdout(['git', '--version'], combineStderr=True,
    #                                             ignoreStderr=True, ignoreExitCode=True)[0])
    print("Python version: %s" % sys.version.split()[0])
    print("Number of cores visible to OS: %d" % multiprocessing.cpu_count())
    print("Free space (GB): %.2f" % sps.getFreeSpace("/", 3))

    hgrc_path = os.path.join(path0, '.hg', 'hgrc')
    if os.path.isfile(hgrc_path):
        print("The hgrc of this repository is:")
        with open(hgrc_path, 'rb') as f:
            hgrc_contents = f.readlines()
        for line in hgrc_contents:
            print(line.rstrip())

    if os.name == 'posix':
        # resource library is only applicable to Linux or Mac platforms.
        import resource  # pylint: disable=import-error
        print("Corefile size (soft limit, hard limit) is: %r" % (resource.getrlimit(resource.RLIMIT_CORE),))


def ensureBuild(options):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    if options.existingBuildDir:
        # Pre-downloaded treeherder builds (browser only for now)
        bDir = options.existingBuildDir  # pylint: disable=invalid-name
        bType = 'local-build'  # pylint: disable=invalid-name
        bSrc = bDir  # pylint: disable=invalid-name
        bRev = ''  # pylint: disable=invalid-name
        manyTimedRunArgs = []  # pylint: disable=invalid-name
    elif not options.useTreeherderBuilds:
        if options.testType == "js":
            # Compiled js shells
            options.build_options = build_options.parseShellOptions(options.build_options)
            options.timeout = options.timeout or machineTimeoutDefaults(options)

            with LockDir(compile_shell.getLockDirPath(options.build_options.repoDir)):
                bRev = hg_helpers.getRepoHashAndId(options.build_options.repoDir)[0]  # pylint: disable=invalid-name
                cshell = compile_shell.CompiledShell(options.build_options, bRev)
                updateLatestTxt = (options.build_options.repoDir == 'mozilla-central')  # pylint: disable=invalid-name
                compile_shell.obtainShell(cshell, updateLatestTxt=updateLatestTxt)

                bDir = cshell.getShellCacheDir()  # pylint: disable=invalid-name
                # Strip out first 3 chars or else the dir name in fuzzing jobs becomes:
                #   js-js-dbg-opt-64-dm-linux
                # This is because options.testType gets prepended along with a dash later.
                bType = build_options.computeShellType(options.build_options)[3:]  # pylint: disable=invalid-name
                bSrc = (  # pylint: disable=invalid-name
                    "Create another shell in shell-cache like this one:\n"
                    'python -u -m %s -b "%s -R %s" -r %s\n\n'
                    "==============================================\n"
                    "|  Fuzzing %s js shell builds\n"
                    "|  DATE: %s\n"
                    "==============================================\n\n" % (
                        "funfuzz.js.compile_shell",
                        options.build_options.build_options_str,
                        options.build_options.repoDir,
                        bRev,
                        cshell.getRepoName(),
                        time.asctime()
                    ))

                manyTimedRunArgs = mtrArgsCreation(options, cshell)  # pylint: disable=invalid-name
                print("buildDir is: %s" % bDir)
                print("buildSrc is: %s" % bSrc)
        else:
            # FIXME: We can probably remove the testType option  # pylint: disable=fixme
            raise Exception('Only testType "js" is supported.')
    else:
        # Treeherder js shells and browser
        # Download from Treeherder and call it 'build'
        # pylint: disable=fixme
        # FIXME: Put 'build' somewhere nicer, like ~/fuzzbuilds/. Don't re-download a build that's up to date.
        # FIXME: randomize branch selection, get appropriate builds, use appropriate known dirs
        bDir = 'build'  # pylint: disable=invalid-name
        bType = download_build.defaultBuildType(options.repoName, None, True)  # pylint: disable=invalid-name
        isJS = options.testType == 'js'  # pylint: disable=invalid-name
        # pylint: disable=invalid-name
        bSrc = download_build.downloadLatestBuild(bType, './', getJsShell=isJS, wantTests=not isJS)
        bRev = ''  # pylint: disable=invalid-name

        # These two lines are only used for treeherder js shells:
        shell = os.path.join(bDir, "dist", "js.exe" if sps.isWin else "js")
        # pylint: disable=invalid-name
        manyTimedRunArgs = ["--random-flags", str(JS_SHELL_DEFAULT_TIMEOUT), "mozilla-central", shell]

    return BuildInfo(bDir, bType, bSrc, bRev, manyTimedRunArgs)


def loopFuzzingAndReduction(options, buildInfo, collector, i):  # pylint: disable=invalid-name,missing-docstring
    tempDir = tempfile.mkdtemp("loop" + str(i))  # pylint: disable=invalid-name
    if options.testType == 'js':
        loop.many_timed_runs(options.targetTime, tempDir, buildInfo.mtrArgs, collector)
    else:
        raise Exception('Only js engine fuzzing is supported')


def machineTimeoutDefaults(options):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Set different defaults depending on the machine type or debugger used."""
    if options.build_options.runWithVg:
        return 300
    elif sps.isARMv7l:
        return 180
    return JS_SHELL_DEFAULT_TIMEOUT


def mtrArgsCreation(options, cshell):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Create many_timed_run arguments for compiled builds."""
    manyTimedRunArgs = []  # pylint: disable=invalid-name
    manyTimedRunArgs.append('--repo=' + sps.normExpUserPath(options.build_options.repoDir))
    manyTimedRunArgs.append("--build=" + options.build_options.build_options_str)
    if options.build_options.runWithVg:
        manyTimedRunArgs.append('--valgrind')
    if options.build_options.enableMoreDeterministic:
        # Treeherder shells not using compare_jit:
        #   They are not built with --enable-more-deterministic - bug 751700
        manyTimedRunArgs.append('--compare-jit')
    manyTimedRunArgs.append('--random-flags')

    # Ordering of elements in manyTimedRunArgs is important.
    manyTimedRunArgs.append(str(options.timeout))
    manyTimedRunArgs.append(cshell.getRepoName())  # known bugs' directory
    manyTimedRunArgs.append(cshell.getShellCacheFullPath())
    return manyTimedRunArgs


if __name__ == "__main__":
    main()

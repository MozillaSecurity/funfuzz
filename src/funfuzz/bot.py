# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Ensures a build is available, then forks a bunch of fuzz-reduce processes.

"""

import io
import multiprocessing
from optparse import OptionParser  # pylint: disable=deprecated-module
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time

from .js import build_options
from .js import compile_shell
from .js import loop
from .util import create_collector
from .util import fork_join
from .util import hg_helpers
from .util import sm_compile_helpers
from .util.lock_dir import LockDir

JS_SHELL_DEFAULT_TIMEOUT = 24  # see comments in loop for tradeoffs


class BuildInfo:  # pylint: disable=missing-param-doc,missing-type-doc,too-few-public-methods
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
        repoName="mozilla-central",
        targetTime=15 * 60,       # 15 minutes
        existingBuildDir=None,
        timeout=0,
        build_options=None,
        useTreeherderBuilds=False,
    )

    parser.add_option("--build", dest="existingBuildDir",
                      help="Use an existing build directory.")

    parser.add_option("--repotype", dest="repoName",
                      help='Sets the repository to be fuzzed. Defaults to "%default".')

    parser.add_option("--target-time", dest="targetTime", type="int",
                      help="Nominal amount of time to run, in seconds")

    parser.add_option("-T", "--use-treeherder-builds", dest="useTreeherderBuilds", action="store_true",
                      help="Download builds from treeherder instead of compiling our own.")

    # Specify how the shell will be built.
    parser.add_option("-b", "--build-options",
                      dest="build_options",
                      help='Specify build options, e.g. -b "-c opt --arch=32" for js '
                           "(python -m funfuzz.js.build_options --help)")

    parser.add_option("--timeout", type="int", dest="timeout",
                      help="Sets the timeout for loop. "
                           "Defaults to taking into account the speed of the computer and debugger (if any).")

    options, args = parser.parse_args()
    if args:
        print("Warning: bot does not use positional arguments")

    if not options.useTreeherderBuilds and not build_options.DEFAULT_TREES_LOCATION.is_dir():
        # We don't have trees, so we must use treeherder builds.
        options.useTreeherderBuilds = True
        print()
        print(f"Trees were absent from default location: {build_options.DEFAULT_TREES_LOCATION}")
        print("Using treeherder builds instead...")
        print()
        sys.exit("Fuzzing downloaded builds is disabled for now, until tooltool is removed. Exiting...")

    if options.build_options is None:
        options.build_options = ""
    if options.useTreeherderBuilds and options.build_options != "":
        raise Exception("Do not use treeherder builds if one specifies build parameters")

    return options


def main():  # pylint: disable=missing-docstring
    print_machine_info()

    options = parseOpts()

    collector = create_collector.make_collector()
    try:
        collector.refresh()
    except RuntimeError:
        print()
        print("Unable to find required entries in FuzzManager. Duplicate detection via sigcache will not work...")

    options.tempDir = tempfile.mkdtemp("fuzzbot")
    print(options.tempDir)

    build_info = ensureBuild(options)
    assert build_info.buildDir.is_dir()

    number_of_processes = multiprocessing.cpu_count()
    if "-asan" in str(build_info.buildDir):
        # This should really be based on the amount of RAM available, but I don't know how to compute that in Python.
        # I could guess 1 GB RAM per core, but that wanders into sketchyville.
        number_of_processes = max(number_of_processes // 2, 1)

    fork_join.forkJoin(options.tempDir, number_of_processes, loopFuzzingAndReduction, options, build_info,
                       collector)

    shutil.rmtree(options.tempDir)


def print_machine_info():
    """Log information about the machine."""
    print(f'Platform details: {" ".join(platform.uname())}')

    hg_version = subprocess.run(["hg", "-q", "version"],
                                check=True,
                                stdout=subprocess.PIPE).stdout.decode("utf-8", errors="replace").rstrip()
    print(f"hg info: {hg_version}")

    if shutil.which("gdb"):
        gdb_version = subprocess.run(["gdb", "--version"],
                                     stdout=subprocess.PIPE).stdout.decode("utf-8", errors="replace").split("\n")[0]
        print(f"gdb info: {gdb_version}")
    if shutil.which("git"):
        git_version = subprocess.run(["git", "version"],
                                     check=True,
                                     stdout=subprocess.PIPE).stdout.decode("utf-8", errors="replace").rstrip()
        print(f"git info: {git_version}")
    print(f"Python version: {sys.version.split()[0]}")

    print(f"Number of cores visible to OS: {multiprocessing.cpu_count()}")
    rootdir_free_space = shutil.disk_usage("/").free / (1024 ** 3)
    print(f"Free space (GB): {rootdir_free_space:.2f}")

    hgrc_path = Path("~/.hg/hgrc").expanduser()
    if hgrc_path.is_file():
        print("The hgrc of this repository is:")
        with io.open(str(hgrc_path), "r", encoding="utf-8", errors="replace") as f:
            hgrc_contents = f.readlines()
        for line in hgrc_contents:
            print(line.rstrip())

    try:
        # resource library is only applicable to Linux or Mac platforms.
        import resource  # pylint: disable=import-error
        # pylint: disable=no-member
        print(f"Corefile size (soft limit, hard limit) is: {resource.getrlimit(resource.RLIMIT_CORE)!r}")
    except ImportError:
        print("Not checking corefile size as resource module is unavailable")


def ensureBuild(options):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    if options.existingBuildDir:
        # Pre-downloaded treeherder builds
        bDir = options.existingBuildDir  # pylint: disable=invalid-name
        bType = "local-build"  # pylint: disable=invalid-name
        bSrc = bDir  # pylint: disable=invalid-name
        bRev = ""  # pylint: disable=invalid-name
        manyTimedRunArgs = []  # pylint: disable=invalid-name
    elif not options.useTreeherderBuilds:
        options.build_options = build_options.parse_shell_opts(options.build_options)
        options.timeout = options.timeout or (300 if options.build_options.runWithVg else JS_SHELL_DEFAULT_TIMEOUT)

        with LockDir(sm_compile_helpers.get_lock_dir_path(Path.home(), options.build_options.repo_dir)):
            bRev = hg_helpers.get_repo_hash_and_id(options.build_options.repo_dir)[0]  # pylint: disable=invalid-name
            cshell = compile_shell.CompiledShell(options.build_options, bRev)
            updateLatestTxt = (options.build_options.repo_dir == "mozilla-central")  # pylint: disable=invalid-name
            compile_shell.obtainShell(cshell, updateLatestTxt=updateLatestTxt)

            bDir = cshell.get_shell_cache_dir()  # pylint: disable=invalid-name
            # Strip out first 3 chars or else the dir name in fuzzing jobs becomes:
            #   js-js-dbg-opt-64-dm-linux
            bType = build_options.computeShellType(options.build_options)[3:]  # pylint: disable=invalid-name
            bSrc = (  # pylint: disable=invalid-name
                f"Create another shell in shell-cache like this one:\n"
                f"python3 -u -m funfuzz.js.compile_shell "
                f'-b "{options.build_options.build_options_str} '
                f'-R {options.build_options.repo_dir}" '
                f"-r {bRev}\n\n"
                f"==============================================\n"
                f"|  Fuzzing {cshell.get_repo_name()} js shell builds\n"
                f"|  DATE: {time.asctime()}\n"
                f"==============================================\n\n"
            )

            manyTimedRunArgs = mtrArgsCreation(options, cshell)  # pylint: disable=invalid-name
            print(f"buildDir is: {bDir}")
            print(f"buildSrc is: {bSrc}")
    else:
        print("TBD: We need to switch to the fuzzfetch repository.")
        sys.exit(0)

    return BuildInfo(bDir, bType, bSrc, bRev, manyTimedRunArgs)


def loopFuzzingAndReduction(options, buildInfo, collector, i):  # pylint: disable=invalid-name,missing-docstring
    tempDir = Path(tempfile.mkdtemp(f"loop{i}"))  # pylint: disable=invalid-name
    loop.many_timed_runs(options.targetTime, tempDir, buildInfo.mtrArgs, collector, False)


def mtrArgsCreation(options, cshell):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Create many_timed_run arguments for compiled builds."""
    manyTimedRunArgs = []  # pylint: disable=invalid-name
    manyTimedRunArgs.append(f"--repo={options.build_options.repo_dir}")
    manyTimedRunArgs.append(f"--build={options.build_options.build_options_str}")
    if options.build_options.runWithVg:
        manyTimedRunArgs.append("--valgrind")
    if options.build_options.enableMoreDeterministic:
        # Treeherder shells not using compare_jit:
        #   They are not built with --enable-more-deterministic - bug 751700
        manyTimedRunArgs.append("--compare-jit")
    manyTimedRunArgs.append("--random-flags")

    # Ordering of elements in manyTimedRunArgs is important.
    manyTimedRunArgs.append(str(options.timeout))
    manyTimedRunArgs.append(cshell.get_repo_name())  # known bugs' directory
    manyTimedRunArgs.append(cshell.get_shell_cache_js_bin_path())
    return manyTimedRunArgs


if __name__ == "__main__":
    main()

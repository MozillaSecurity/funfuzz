# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Allows specification of build configuration parameters.
"""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import argparse
from builtins import object
import hashlib
import io
import logging
import platform
import random
import sys

from past.builtins import range

from ..util import hg_helpers

if sys.version_info.major == 2:
    from pathlib2 import Path  # pylint: disable=import-error
else:
    from pathlib import Path  # pylint: disable=import-error

FUNFUZZ_LOG = logging.getLogger("funfuzz")
logging.basicConfig(level=logging.DEBUG)

DEFAULT_TREES_LOCATION = Path.home() / "trees"


def chance(p):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    return random.random() < p


class Randomizer(object):  # pylint: disable=missing-docstring
    def __init__(self):
        self.options = []

    def add(self, name, fastDeviceWeight, slowDeviceWeight):  # pylint: disable=invalid-name,missing-docstring
        self.options.append({
            "name": name,
            "fastDeviceWeight": fastDeviceWeight,
            "slowDeviceWeight": slowDeviceWeight,
        })

    def getRandomSubset(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc
        def getWeight(o):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
            return o["slowDeviceWeight"]
        return [o["name"] for o in self.options if chance(getWeight(o))]


def addParserOptions():  # pylint: disable=invalid-name,missing-return-doc,missing-return-type-doc
    """Add parser options."""
    # Where to find the source dir and compiler, patching if necessary.
    parser = argparse.ArgumentParser(description="Usage: Don't use this directly")
    randomizer = Randomizer()

    def randomizeBool(name, fastDeviceWeight, slowDeviceWeight, **kwargs):  # pylint: disable=invalid-name
        # pylint: disable=missing-param-doc,missing-type-doc
        """Add a randomized boolean option that defaults to False.

        Option also has a [weight] chance of being changed to True when using --random.
        """
        randomizer.add(name[-1], fastDeviceWeight, slowDeviceWeight)
        parser.add_argument(*name, action="store_true", default=False, **kwargs)

    parser.add_argument("--random",
                        dest="enableRandom",
                        action="store_true",
                        default=False,
                        help='Chooses sensible random build options. Defaults to "%(default)s".')
    parser.add_argument("-R", "--repodir",
                        dest="repo_dir",
                        type=Path,
                        help="Sets the source repository.")
    parser.add_argument("-P", "--patch",
                        dest="patch_file",
                        type=Path,
                        help="Define the path to a single JS patch. Ensure mq is installed.")

    # Basic spidermonkey options
    randomizeBool(["--32"], 0.5, 0.5,
                  dest="enable32",
                  help="Build 32-bit shells, but if not enabled, 64-bit shells are built.")
    randomizeBool(["--enable-debug"], 0.5, 0.5,
                  dest="enableDbg",
                  help='Build shells with --enable-debug. Defaults to "%(default)s". '
                       "Currently defaults to True in configure.in on mozilla-central.")
    randomizeBool(["--disable-debug"], 0, 0,
                  dest="disableDbg",
                  help='Build shells with --disable-debug. Defaults to "%(default)s". '
                       "Currently defaults to True in configure.in on mozilla-central.")
    randomizeBool(["--enable-optimize"], 0, 0,
                  dest="enableOpt",
                  help='Build shells with --enable-optimize. Defaults to "%(default)s".')
    randomizeBool(["--disable-optimize"], 0.1, 0.01,
                  dest="disableOpt",
                  help='Build shells with --disable-optimize. Defaults to "%(default)s".')
    randomizeBool(["--enable-profiling"], 0, 0,
                  dest="enableProfiling",
                  help='Build shells with --enable-profiling. Defaults to "%(default)s". '
                       "Currently defaults to True in configure.in on mozilla-central.")
    randomizeBool(["--disable-profiling"], 0.5, 0,
                  dest="disableProfiling",
                  help='Build with profiling off. Defaults to "True" on Linux, else "%(default)s".')

    # Alternative compiler for Linux and Windows. Clang is always turned on, on Macs.
    randomizeBool(["--build-with-clang"], 0.5, 0.5,
                  dest="buildWithClang",
                  help='Build with clang. Defaults to "True" on Macs, "%(default)s" otherwise.')
    # Memory debuggers
    randomizeBool(["--build-with-asan"], 0.3, 0,
                  dest="buildWithAsan",
                  help='Build with clang AddressSanitizer support. Defaults to "%(default)s".')
    randomizeBool(["--build-with-valgrind"], 0.2, 0.05,
                  dest="buildWithVg",
                  help='Build with valgrind.h bits. Defaults to "%(default)s". '
                       "Requires --enable-hardfp for ARM platforms.")
    # We do not use randomizeBool because we add this flag automatically if --build-with-valgrind
    # is selected.
    parser.add_argument("--run-with-valgrind",
                        dest="runWithVg",
                        action="store_true",
                        default=False,
                        help="Run the shell under Valgrind. Requires --build-with-valgrind.")

    # Misc spidermonkey options
    randomizeBool(["--enable-more-deterministic"], 0.75, 0.5,
                  dest="enableMoreDeterministic",
                  help='Build shells with --enable-more-deterministic. Defaults to "%(default)s".')
    parser.add_argument("--enable-oom-breakpoint",  # Extra debugging help for OOM assertions
                        dest="enableOomBreakpoint",
                        action="store_true",
                        default=False,
                        help='Build shells with --enable-oom-breakpoint. Defaults to "%(default)s".')
    parser.add_argument("--without-intl-api",  # Speeds up compilation but is non-default
                        dest="enableWithoutIntlApi",
                        action="store_true",
                        default=False,
                        help='Build shells using --without-intl-api. Defaults to "%(default)s".')
    randomizeBool(["--enable-simulator=arm"], 0.3, 0,
                  dest="enableSimulatorArm32",
                  help="Build shells with --enable-simulator=arm, only applicable to 32-bit shells. "
                       'Defaults to "%(default)s".')
    randomizeBool(["--enable-simulator=arm64"], 0.3, 0,
                  dest="enableSimulatorArm64",
                  help="Build shells with --enable-simulator=arm64, only applicable to 64-bit shells. "
                       'Defaults to "%(default)s".')
    parser.add_argument("--enable-arm-simulator",
                        dest="enableArmSimulatorObsolete",
                        action="store_true",
                        default=False,
                        help="Build the shell using --enable-arm-simulator for legacy purposes. "
                             "This flag is obsolete and is the equivalent of --enable-simulator=arm, "
                             'use --enable-simulator=[arm|arm64] instead. Defaults to "%(default)s".')

    # If adding a new compile option, be mindful of repository randomization.
    # e.g. it may be in mozilla-central but not in mozilla-beta

    return parser, randomizer


def parse_shell_opts(args):  # pylint: disable=too-many-branches
    """Parses shell options into a build_options object.

    Args:
        args (object): Arguments to be parsed

    Returns:
        build_options: An immutable build_options object
    """
    parser, randomizer = addParserOptions()
    build_options = parser.parse_args(args.split())

    if platform.system() == "Darwin":
        build_options.buildWithClang = True  # Clang seems to be the only supported compiler

    if build_options.enableArmSimulatorObsolete:
        build_options.enableSimulatorArm32 = True

    if build_options.enableRandom:
        build_options = generateRandomConfigurations(parser, randomizer)
    else:
        build_options.build_options_str = args
        valid = areArgsValid(build_options)
        if not valid[0]:
            FUNFUZZ_LOG.info("WARNING: This set of build options is not tested well because: %s", valid[1])

    # Ensures releng machines do not enter the if block and assumes mozilla-central always exists
    if DEFAULT_TREES_LOCATION.is_dir():  # pylint: disable=no-member
        # Repositories do not get randomized if a repository is specified.
        if build_options.repo_dir:
            build_options.repo_dir = build_options.repo_dir.expanduser()
        else:
            # For patch fuzzing without a specified repo, do not randomize repos, assume m-c instead
            if build_options.enableRandom and not build_options.patch_file:
                build_options.repo_dir = get_random_valid_repo(DEFAULT_TREES_LOCATION)
            else:
                build_options.repo_dir = DEFAULT_TREES_LOCATION / "mozilla-central"

            if not build_options.repo_dir.is_dir():
                sys.exit("repo_dir is not specified, and a default repository location cannot be confirmed. Exiting...")

        assert (build_options.repo_dir / ".hg" / "hgrc").is_file()

        if build_options.patch_file:
            hg_helpers.ensure_mq_enabled()
            assert build_options.patch_file.resolve().is_file()
    else:
        sys.exit("DEFAULT_TREES_LOCATION not found at: %s. Exiting..." % DEFAULT_TREES_LOCATION)

    return build_options


def computeShellType(build_options):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc,too-complex
    """Return configuration information of the shell."""
    fileName = ["js"]  # pylint: disable=invalid-name
    if build_options.enableDbg:
        fileName.append("dbg")
    if build_options.disableOpt:
        fileName.append("optDisabled")
    fileName.append("32" if build_options.enable32 else "64")
    if build_options.enableProfiling:
        fileName.append("prof")
    if build_options.disableProfiling:
        fileName.append("profDisabled")
    if build_options.enableMoreDeterministic:
        fileName.append("dm")
    if build_options.buildWithClang:
        fileName.append("clang")
    if build_options.buildWithAsan:
        fileName.append("asan")
    if build_options.buildWithVg:
        fileName.append("vg")
    if build_options.enableOomBreakpoint:
        fileName.append("oombp")
    if build_options.enableWithoutIntlApi:
        fileName.append("intlDisabled")
    if build_options.enableSimulatorArm32 or build_options.enableSimulatorArm64:
        fileName.append("armSim")
    fileName.append("windows" if platform.system() == "Windows" else platform.system().lower())
    if build_options.patch_file:
        # We take the name before the first dot, so Windows (hopefully) does not get confused.
        fileName.append(build_options.patch_file.name)
        with io.open(str(build_options.patch_file.resolve()), "r", encoding="utf-8", errors="replace") as f:
            readResult = f.read()  # pylint: disable=invalid-name
        # Append the patch hash, but this is not equivalent to Mercurial's hash of the patch.
        fileName.append(hashlib.sha512(readResult).hexdigest()[:12])

    assert "" not in fileName, 'fileName "' + repr(fileName) + '" should not have empty elements.'
    return "-".join(fileName)


def computeShellName(build_options, buildRev):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Return the shell type together with the build revision."""
    return computeShellType(build_options) + "-" + buildRev


def areArgsValid(args):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc,missing-return-type-doc
    # pylint: disable=missing-type-doc,too-many-branches,too-complex,too-many-return-statements
    """Check to see if chosen arguments are valid."""
    # Consider refactoring this to raise exceptions instead.
    if args.enableDbg and args.disableDbg:
        return False, "Making a debug, non-debug build would be contradictory."
    if args.enableOpt and args.disableOpt:
        return False, "Making an optimized, non-optimized build would be contradictory."
    if not args.enableDbg and args.disableOpt:
        return False, "Making a non-debug, non-optimized build would be kind of silly."

    if platform.system() == "Darwin" and args.enable32:
        return False, "We are no longer going to ship 32-bit Mac binaries."
    if "Microsoft" in platform.release() and args.enable32:
        return False, "WSL does not seem to support 32-bit Linux binaries yet."

    if args.buildWithVg:
        return False, "FIXME: We need to set LD_LIBRARY_PATH first, else Valgrind segfaults."
        # Test with leak-checking disabled, test that reporting works, test only on x64 16.04
        # Test with bug 1278887
        # Also ensure we are running autobisectjs w/Valgrind having the --error-exitcode=?? flag
        # Uncomment the following when we unbreak Valgrind fuzzing.
        # if not which("valgrind"):
        #     return False, "Valgrind is not installed."
        # if not args.enableOpt:
        #     # FIXME: Isn't this enabled by default??  # pylint: disable=fixme
        #     return False, "Valgrind needs opt builds."
        # if args.buildWithAsan:
        #     return False, "One should not compile with both Valgrind flags and ASan flags."

        # if platform.system() == "Windows":
        #     return False, "Valgrind does not work on Windows."
        # if platform.system() == "Darwin":
        #     return False, "Valgrind does not work well with Mac OS X 10.10 Yosemite."

    if args.runWithVg and not args.buildWithVg:
        return False, "--run-with-valgrind needs --build-with-valgrind."

    if args.buildWithClang:
        if platform.system() == "Linux" and not args.buildWithAsan:
            return False, "We do not really care about non-Asan clang-compiled Linux builds yet."
        if platform.system() == "Windows":
            return False, "Clang builds on Windows are not supported well yet."

    if args.buildWithAsan:
        if not args.buildWithClang:
            return False, "We should test ASan builds that are only compiled with Clang."
        # Also check for determinism to prevent LLVM compilation from happening on releng machines,
        # since releng machines only test non-deterministic builds.
        if not args.enableMoreDeterministic:
            return False, "We should test deterministic ASan builds."
        if platform.system() == "Linux":  # https://github.com/MozillaSecurity/funfuzz/issues/25
            return False, "Linux ASan builds cannot yet submit to FuzzManager."
        if platform.system() == "Darwin":  # https://github.com/MozillaSecurity/funfuzz/issues/25
            return False, "Mac ASan builds cannot yet submit to FuzzManager."
        if platform.system() == "Windows":
            return False, "Asan is not yet supported on Windows."

    if args.enableSimulatorArm32 or args.enableSimulatorArm64:
        if platform.system() == "Windows":
            return False, "Nobody runs the ARM simulator on Windows."
        if args.enableSimulatorArm32 and not args.enable32:
            return False, "The 32-bit ARM simulator builds are only for 32-bit binaries."
        if args.enableSimulatorArm64 and args.enable32:
            return False, "The 64-bit ARM simulator builds are only for 64-bit binaries."
        if args.enableSimulatorArm64 and not args.enable32:
            return False, "The 64-bit ARM simulator builds are not ready for testing yet."

    return True, ""


def generateRandomConfigurations(parser, randomizer):  # pylint: disable=invalid-name
    # pylint: disable=missing-docstring,missing-return-doc,missing-return-type-doc
    while True:
        randomArgs = randomizer.getRandomSubset()  # pylint: disable=invalid-name
        if "--build-with-valgrind" in randomArgs and chance(0.95):
            randomArgs.append("--run-with-valgrind")
        build_options = parser.parse_args(randomArgs)
        if areArgsValid(build_options)[0]:
            build_options.build_options_str = " ".join(randomArgs)  # Used for autobisectjs
            build_options.enableRandom = True  # This has to be true since we are randomizing...
            return build_options


def get_random_valid_repo(tree):
    """Given a path to Mozilla Mercurial repositories, return a randomly chosen valid one.

    Args:
        tree (Path): Intended location of Mozilla Mercurial repositories

    Returns:
        Path: Location of a valid Mozilla repository
    """
    assert isinstance(tree, Path)
    tree = tree.resolve()

    valid_repos = []
    for branch in ["mozilla-central", "mozilla-beta"]:
        if (tree / branch / ".hg" / "hgrc").is_file():
            valid_repos.append(branch)

    # After checking if repos are valid, reduce chances that non-mozilla-central repos are chosen
    if "mozilla-beta" in valid_repos and chance(0.5):
        valid_repos.remove("mozilla-beta")

    return tree / random.choice(valid_repos)


def main():  # pylint: disable=missing-docstring
    FUNFUZZ_LOG.info("Here are some sample random build configurations that can be generated:")
    parser, randomizer = addParserOptions()
    build_options = parser.parse_args()

    if build_options.enableArmSimulatorObsolete:
        build_options.enableSimulatorArm32 = True

    for _ in range(30):
        build_options = generateRandomConfigurations(parser, randomizer)
        FUNFUZZ_LOG.info(build_options.build_options_str)

    FUNFUZZ_LOG.info("")
    FUNFUZZ_LOG.info("Running this file directly doesn't do anything, but here's our subparser help:")
    FUNFUZZ_LOG.info("")
    parse_shell_opts("--help")


if __name__ == "__main__":
    main()

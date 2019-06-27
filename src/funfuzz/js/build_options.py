# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Allows specification of build configuration parameters.
"""

import argparse
import hashlib
import io
from pathlib import Path
import platform
import random
import sys

from ..util import hg_helpers

DEFAULT_TREES_LOCATION = Path.home() / "trees"


def chance(i):
    """Returns a random boolean result based on an input probability.

    Args:
        i (float): Intended probability.

    Returns:
        bool: Result based on the input probability
    """
    return random.random() < i


class Randomizer:  # pylint: disable=missing-docstring
    def __init__(self):
        self.options = []

    def add(self, name, weight):  # pylint: disable=invalid-name,missing-docstring
        self.options.append({
            "name": name,
            "weight": weight,
        })

    def getRandomSubset(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc
        def getWeight(o):  # pylint: disable=invalid-name,missing-return-doc
            return o["weight"]
        return [o["name"] for o in self.options if chance(getWeight(o))]


def addParserOptions():  # pylint: disable=invalid-name,missing-return-doc,missing-return-type-doc
    """Add parser options."""
    # Where to find the source dir and compiler, patching if necessary.
    parser = argparse.ArgumentParser(description="Usage: Don't use this directly")
    randomizer = Randomizer()

    def randomizeBool(name, weight, **kwargs):  # pylint: disable=invalid-name
        # pylint: disable=missing-param-doc,missing-type-doc
        """Add a randomized boolean option that defaults to False.

        Option also has a [weight] chance of being changed to True when using --random.
        """
        randomizer.add(name[-1], weight)
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
    randomizeBool(["--32"], 0.5,
                  dest="enable32",
                  help="Build 32-bit shells, but if not enabled, 64-bit shells are built.")
    randomizeBool(["--enable-debug"], 0.5,
                  dest="enableDbg",
                  help='Build shells with --enable-debug. Defaults to "%(default)s". '
                       "Currently defaults to True in configure.in on mozilla-central.")
    randomizeBool(["--disable-debug"], 0,
                  dest="disableDbg",
                  help='Build shells with --disable-debug. Defaults to "%(default)s". '
                       "Currently defaults to True in configure.in on mozilla-central.")
    randomizeBool(["--enable-optimize"], 0,
                  dest="enableOpt",
                  help='Build shells with --enable-optimize. Defaults to "%(default)s".')
    randomizeBool(["--disable-optimize"], 0.1,
                  dest="disableOpt",
                  help='Build shells with --disable-optimize. Defaults to "%(default)s".')
    randomizeBool(["--disable-profiling"], 0.5,
                  dest="disableProfiling",
                  help='Build with profiling off. Defaults to "True" on Linux, else "%(default)s".')

    # Memory debuggers
    randomizeBool(["--enable-address-sanitizer"], 0.3,
                  dest="enableAddressSanitizer",
                  help='Build with clang AddressSanitizer support. Defaults to "%(default)s".')
    randomizeBool(["--enable-valgrind"], 0.2,
                  dest="enableValgrind",
                  help='Build with valgrind.h bits. Defaults to "%(default)s". '
                       "Requires --enable-hardfp for ARM platforms.")
    # We do not use randomizeBool because we add this flag automatically if --enable-valgrind
    # is selected.
    parser.add_argument("--run-with-valgrind",
                        dest="runWithVg",
                        action="store_true",
                        default=False,
                        help="Run the shell under Valgrind. Requires --enable-valgrind.")

    # Misc spidermonkey options
    randomizeBool(["--enable-more-deterministic"], 0.75,
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
    randomizeBool(["--enable-simulator=arm"], 0.3,
                  dest="enableSimulatorArm32",
                  help="Build shells with --enable-simulator=arm, only applicable to 32-bit shells. "
                       'Defaults to "%(default)s".')
    randomizeBool(["--enable-simulator=arm64"], 0.3,
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


def parse_shell_opts(args):  # pylint: disable=too-complex,too-many-branches
    """Parses shell options into a build_options object.

    Args:
        args (object): Arguments to be parsed

    Returns:
        build_options: An immutable build_options object
    """
    parser, randomizer = addParserOptions()
    build_options = parser.parse_args(args.split())

    if build_options.enableArmSimulatorObsolete:
        build_options.enableSimulatorArm32 = True

    if build_options.enableRandom:
        build_options = generateRandomConfigurations(parser, randomizer)
    else:
        build_options.build_options_str = args
        valid = areArgsValid(build_options)
        if not valid[0]:
            print(f"WARNING: This set of build options is not tested well because: {valid[1]}")

    if build_options.patch_file:
        build_options.patch_file = build_options.patch_file.expanduser().resolve()

    # Ensures releng machines do not enter the if block and assumes mozilla-central always exists
    if DEFAULT_TREES_LOCATION.is_dir():
        # Repositories do not get randomized if a repository is specified.
        if build_options.repo_dir:
            build_options.repo_dir = build_options.repo_dir.expanduser()
        else:
            build_options.repo_dir = DEFAULT_TREES_LOCATION / "mozilla-central"

            if not build_options.repo_dir.is_dir():
                sys.exit("repo_dir is not specified, and a default repository location cannot be confirmed. Exiting...")

        assert (build_options.repo_dir / ".hg" / "hgrc").is_file()

        if build_options.patch_file:
            hg_helpers.ensure_mq_enabled()
            assert build_options.patch_file.is_file()
    else:
        sys.exit(f"DEFAULT_TREES_LOCATION not found at: {DEFAULT_TREES_LOCATION}. Exiting...")

    return build_options


def computeShellType(build_options):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc,too-complex,too-many-branches
    """Return configuration information of the shell."""
    fileName = ["js"]  # pylint: disable=invalid-name
    if build_options.enableDbg:
        fileName.append("dbg")
    if build_options.disableOpt:
        fileName.append("optDisabled")
    fileName.append("32" if build_options.enable32 else "64")
    if build_options.disableProfiling:
        fileName.append("profDisabled")
    if build_options.enableMoreDeterministic:
        fileName.append("dm")
    if build_options.enableAddressSanitizer:
        fileName.append("asan")
    if build_options.enableValgrind:
        fileName.append("vg")
    if build_options.enableOomBreakpoint:
        fileName.append("oombp")
    if build_options.enableWithoutIntlApi:
        fileName.append("intlDisabled")
    if build_options.enableSimulatorArm32:
        fileName.append("armsim32")
    if build_options.enableSimulatorArm64:
        fileName.append("armsim64")
    fileName.append(platform.system().lower())
    fileName.append(platform.machine().lower())
    if build_options.patch_file:
        # We take the name before the first dot, so Windows (hopefully) does not get confused.
        # Also replace any "." in the name with "_" so pathlib .stem and suffix-wrangling work properly
        fileName.append(build_options.patch_file.name.replace(".", "_"))
        with io.open(str(build_options.patch_file), "r", encoding="utf-8", errors="replace") as f:
            readResult = f.read()  # pylint: disable=invalid-name
        # Append the patch hash, but this is not equivalent to Mercurial's hash of the patch.
        fileName.append(hashlib.sha512(readResult.encode("utf-8")).hexdigest()[:12])

    assert "" not in fileName, f'fileName "{fileName!r}" should not have empty elements.'
    return "-".join(fileName)


def computeShellName(build_options, buildRev):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Return the shell type together with the build revision."""
    return f"{computeShellType(build_options)}-{buildRev}"


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
    if platform.machine() == "aarch64" and args.enable32:
        return False, "ARM64 systems cannot seem to compile 32-bit binaries properly."
    if "Microsoft" in platform.release() and args.enable32:
        return False, "WSL does not seem to support 32-bit Linux binaries yet."

    if args.enableValgrind:
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
        # if args.enableAddressSanitizer:
        #     return False, "One should not compile with both Valgrind flags and ASan flags."

        # if platform.system() == "Windows":
        #     return False, "Valgrind does not work on Windows."
        # if platform.system() == "Darwin":
        #     return False, "Valgrind does not work well with Mac OS X 10.10 Yosemite."

    if args.runWithVg and not args.enableValgrind:
        return False, "--run-with-valgrind needs --enable-valgrind."

    if args.enableAddressSanitizer:
        if args.enable32:
            return False, "32-bit ASan builds fail on 18.04 due to https://github.com/google/sanitizers/issues/954."
        if platform.system() == "Linux" and "Microsoft" in platform.release():
            return False, "Linux ASan builds cannot yet work in WSL though there may be workarounds."
        if platform.system() == "Windows" and args.enable32:
            return False, "ASan is explicitly not supported in 32-bit Windows builds."
        if platform.system() == "Windows":
            return False, "Windows ASan builds still seem to run into issues."

    if args.enableSimulatorArm32 or args.enableSimulatorArm64:
        if platform.system() == "Windows" and args.enableSimulatorArm32:
            return False, "Nobody runs the ARM32 simulators on Windows."
        if platform.system() == "Windows" and args.enableSimulatorArm64:
            return False, "Nobody runs the ARM64 simulators on Windows."
        if platform.system() == "Linux" and platform.machine() == "aarch64" and args.enableSimulatorArm32:
            return False, "Nobody runs the ARM32 simulators on ARM64 Linux."
        if platform.system() == "Linux" and platform.machine() == "aarch64" and args.enableSimulatorArm64:
            return False, "Nobody runs the ARM64 simulators on ARM64 Linux."
        if args.enableSimulatorArm32 and not args.enable32:
            return False, "The 32-bit ARM simulator builds are only for 32-bit binaries."
        if args.enableSimulatorArm64 and args.enable32:
            return False, "The 64-bit ARM simulator builds are only for 64-bit binaries."

    return True, ""


def generateRandomConfigurations(parser, randomizer):  # pylint: disable=invalid-name
    # pylint: disable=missing-docstring,missing-return-doc,missing-return-type-doc
    while True:
        randomArgs = randomizer.getRandomSubset()  # pylint: disable=invalid-name
        if "--enable-valgrind" in randomArgs and chance(0.95):
            randomArgs.append("--run-with-valgrind")
        build_options = parser.parse_args(randomArgs)
        if areArgsValid(build_options)[0]:
            build_options.build_options_str = " ".join(randomArgs)  # Used for autobisectjs
            build_options.enableRandom = True  # This has to be true since we are randomizing...
            return build_options


def main():  # pylint: disable=missing-docstring
    print("Here are some sample random build configurations that can be generated:")
    parser, randomizer = addParserOptions()

    for _ in range(30):
        build_options = generateRandomConfigurations(parser, randomizer)
        print(build_options.build_options_str)

    print()
    print("Running this file directly doesn't do anything, but here's our subparser help:")
    print()
    parser.parse_args()


if __name__ == "__main__":
    main()

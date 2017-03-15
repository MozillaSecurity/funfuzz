#!/usr/bin/env python

from __future__ import absolute_import

import argparse
import hashlib
import os
import platform
import random
import sys

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
import hgCmds
import subprocesses as sps

DEFAULT_TREES_LOCATION = sps.normExpUserPath(os.path.join('~', 'trees'))
deviceIsFast = not sps.isARMv7l


def chance(p):
    return random.random() < p


class Randomizer(object):
    def __init__(self):
        self.options = []

    def add(self, name, fastDeviceWeight, slowDeviceWeight):
        self.options.append({
            'name': name,
            'fastDeviceWeight': fastDeviceWeight,
            'slowDeviceWeight': slowDeviceWeight
        })

    def getRandomSubset(self):
        def getWeight(o):
            return o['fastDeviceWeight'] if deviceIsFast else o['slowDeviceWeight']
        return [o['name'] for o in self.options if chance(getWeight(o))]


def addParserOptions():
    """Add parser options."""
    # Where to find the source dir and compiler, patching if necessary.
    parser = argparse.ArgumentParser(description="Usage: Don't use this directly")
    randomizer = Randomizer()

    def randomizeBool(name, fastDeviceWeight, slowDeviceWeight, **kwargs):
        """Add a randomized boolean option that defaults to False.

        Option also has a [weight] chance of being changed to True when using --random.
        """
        randomizer.add(name[-1], fastDeviceWeight, slowDeviceWeight)
        parser.add_argument(*name, action='store_true', default=False, **kwargs)

    parser.add_argument('--random',
                        dest='enableRandom',
                        action='store_true',
                        default=False,
                        help='Chooses sensible random build options. Defaults to "%(default)s".')
    parser.add_argument('-R', '--repoDir',
                        dest='repoDir',
                        help='Sets the source repository.')
    parser.add_argument('-P', '--patch',
                        dest='patchFile',
                        help='Define the path to a single JS patch. Ensure mq is installed.')

    # Basic spidermonkey options
    randomizeBool(['--32'], 0.5, 0.5,
                  dest='enable32',
                  help='Build 32-bit shells, but if not enabled, 64-bit shells are built.')
    randomizeBool(['--enable-debug'], 0.5, 0.5,
                  dest='enableDbg',
                  help='Build shells with --enable-debug. Defaults to "%(default)s". ' + \
                       'Currently defaults to True in configure.in on mozilla-central.')
    randomizeBool(['--disable-debug'], 0, 0,
                  dest='disableDbg',
                  help='Build shells with --disable-debug. Defaults to "%(default)s". ' + \
                       'Currently defaults to True in configure.in on mozilla-central.')
    randomizeBool(['--enable-optimize'], 0, 0,
                  dest='enableOpt',
                  help='Build shells with --enable-optimize. Defaults to "%(default)s".')
    randomizeBool(['--disable-optimize'], 0.1, 0.01,
                  dest='disableOpt',
                  help='Build shells with --disable-optimize. Defaults to "%(default)s".')
    randomizeBool(['--enable-profiling'], 0, 0,
                  dest='enableProfiling',
                  help='Build shells with --enable-profiling. Defaults to "%(default)s". ' + \
                       'Currently defaults to True in configure.in on mozilla-central.')
    randomizeBool(['--disable-profiling'], 0.5, 0,
                  dest='disableProfiling',
                  help='Build with profiling off. Defaults to "True" on Linux, else "%(default)s".')

    # Alternative compiler for Linux and Windows. Clang is always turned on, on Macs.
    randomizeBool(['--build-with-clang'], 0.5, 0.5,
                  dest='buildWithClang',
                  help='Build with clang. Defaults to "True" on Macs, "%(default)s" otherwise.')
    # Memory debuggers
    randomizeBool(['--build-with-asan'], 0.3, 0,
                  dest='buildWithAsan',
                  help='Build with clang AddressSanitizer support. Defaults to "%(default)s".')
    randomizeBool(['--build-with-valgrind'], 0.2, 0.05,
                  dest='buildWithVg',
                  help='Build with valgrind.h bits. Defaults to "%(default)s". ' +
                  'Requires --enable-hardfp for ARM platforms.')
    # We do not use randomizeBool because we add this flag automatically if --build-with-valgrind
    # is selected.
    parser.add_argument('--run-with-valgrind',
                        dest='runWithVg',
                        action='store_true',
                        default=False,
                        help='Run the shell under Valgrind. Requires --build-with-valgrind.')

    # Misc spidermonkey options
    if sps.isARMv7l:
        randomizeBool(['--enable-hardfp'], 0.1, 0.1,
                      dest='enableHardFp',
                      help='Build hardfp shells (ARM-specific setting). Defaults to "%(default)s".')
    randomizeBool(['--enable-more-deterministic'], 0.75, 0.5,
                  dest='enableMoreDeterministic',
                  help='Build shells with --enable-more-deterministic. Defaults to "%(default)s".')
    parser.add_argument('--enable-oom-breakpoint',  # Extra debugging help for OOM assertions
                        dest='enableOomBreakpoint',
                        action='store_true',
                        default=False,
                        help='Build shells with --enable-oom-breakpoint. ' +
                        'Defaults to "%(default)s".')
    parser.add_argument('--without-intl-api',  # Speeds up compilation but is non-default
                        dest='enableWithoutIntlApi',
                        action='store_true',
                        default=False,
                        help='Build shells using --without-intl-api. ' +
                        'Defaults to "%(default)s".')
    randomizeBool(['--enable-simulator=arm'], 0.3, 0,
                  dest='enableSimulatorArm32',
                  help='Build shells with --enable-simulator=arm, only applicable to 32-bit shells. ' +
                  'Defaults to "%(default)s".')
    randomizeBool(['--enable-simulator=arm64'], 0.3, 0,
                  dest='enableSimulatorArm64',
                  help='Build shells with --enable-simulator=arm64, only applicable to 64-bit shells. ' +
                  'Defaults to "%(default)s".')
    parser.add_argument('--enable-arm-simulator',
                        dest='enableArmSimulatorObsolete',
                        action='store_true',
                        default=False,
                        help='Build the shell using --enable-arm-simulator for legacy purposes. ' +
                        'This flag is obsolete and is the equivalent of --enable-simulator=arm, ' +
                        'use --enable-simulator=[arm|arm64] instead. ' +
                        'Defaults to "%(default)s".')

    # If adding a new compile option, be mindful of repository randomization.
    # e.g. it may be in mozilla-central but not in mozilla-aurora/beta/esr45

    return parser, randomizer


def parseShellOptions(inputArgs):
    """Return a 'buildOptions' object, which is intended to be immutable."""
    parser, randomizer = addParserOptions()
    buildOptions = parser.parse_args(inputArgs.split())

    if sps.isMac:
        buildOptions.buildWithClang = True  # Clang seems to be the only supported compiler

    if buildOptions.enableArmSimulatorObsolete:
        buildOptions.enableSimulatorArm32 = True

    if buildOptions.enableRandom:
        buildOptions = generateRandomConfigurations(parser, randomizer)
    else:
        buildOptions.buildOptionsStr = inputArgs
        valid = areArgsValid(buildOptions)
        if not valid[0]:
            print 'WARNING: This set of build options is not tested well because: ' + valid[1]

    # Ensures releng machines do not enter the if block and assumes mozilla-central always exists
    if os.path.isdir(DEFAULT_TREES_LOCATION):
        # Repositories do not get randomized if a repository is specified.
        if buildOptions.repoDir is None:
            # For patch fuzzing without a specified repo, do not randomize repos, assume m-c instead
            if buildOptions.enableRandom and not buildOptions.patchFile:
                buildOptions.repoDir = getRandomValidRepo(DEFAULT_TREES_LOCATION)
            else:
                buildOptions.repoDir = os.path.realpath(sps.normExpUserPath(
                    os.path.join(DEFAULT_TREES_LOCATION, 'mozilla-central')))

        assert hgCmds.isRepoValid(buildOptions.repoDir)

        if buildOptions.patchFile:
            hgCmds.ensureMqEnabled()
            buildOptions.patchFile = sps.normExpUserPath(buildOptions.patchFile)
            assert os.path.isfile(buildOptions.patchFile)

    return buildOptions


def computeShellType(buildOptions):
    """Return configuration information of the shell."""
    fileName = ['js']
    if buildOptions.enableDbg:
        fileName.append('dbg')
    if buildOptions.disableOpt:
        fileName.append('optDisabled')
    fileName.append('32' if buildOptions.enable32 else '64')
    if buildOptions.enableProfiling:
        fileName.append('prof')
    if buildOptions.disableProfiling:
        fileName.append('profDisabled')
    if buildOptions.enableMoreDeterministic:
        fileName.append('dm')
    if buildOptions.buildWithClang:
        fileName.append('clang')
    if buildOptions.buildWithAsan:
        fileName.append('asan')
    if buildOptions.buildWithVg:
        fileName.append('vg')
    if buildOptions.enableOomBreakpoint:
        fileName.append('oombp')
    if buildOptions.enableWithoutIntlApi:
        fileName.append('intlDisabled')
    if buildOptions.enableSimulatorArm32 or buildOptions.enableSimulatorArm64:
        fileName.append('armSim')
    if sps.isARMv7l:
        fileName.append('armhfp' if buildOptions.enableHardFp else 'armsfp')
    fileName.append('windows' if sps.isWin else platform.system().lower())
    if buildOptions.patchFile:
        # We take the name before the first dot, so Windows (hopefully) does not get confused.
        fileName.append(os.path.basename(buildOptions.patchFile).split('.')[0])
        # Append the patch hash, but this is not equivalent to Mercurial's hash of the patch.
        fileName.append(hashlib.sha512(file(os.path.abspath(buildOptions.patchFile), 'rb').read())
                        .hexdigest()[:12])

    assert '' not in fileName, 'fileName "' + repr(fileName) + '" should not have empty elements.'
    return '-'.join(fileName)


def computeShellName(buildOptions, buildRev):
    """Return the shell type together with the build revision."""
    return computeShellType(buildOptions) + '-' + buildRev


def areArgsValid(args):
    """Check to see if chosen arguments are valid."""
    if args.enableDbg and args.disableDbg:
        return False, 'Making a debug, non-debug build would be contradictory.'
    if args.enableOpt and args.disableOpt:
        return False, 'Making an optimized, non-optimized build would be contradictory.'
    if not args.enableDbg and args.disableOpt:
        return False, 'Making a non-debug, non-optimized build would be kind of silly.'
    if sps.isARMv7l and not args.enable32:
        return False, '64-bit ARM builds are not yet supported.'

    if sps.isWin and (args.enable32 == sps.isMozBuild64):
        return False, 'Win32 builds need the 32-bit MozillaBuild batch file and likewise the ' + \
            'corresponding 64-bit ones for Win64 builds.'

    if args.buildWithVg:
        return False, 'FIXME: We need to set LD_LIBRARY_PATH first, else Valgrind segfaults.'
        # Also ensure we are running autoBisect w/Valgrind having the --error-exitcode=?? flag
        # Uncomment the following when we unbreak Valgrind fuzzing.
        # if not sps.isProgramInstalled('valgrind'):
        #     return False, 'Valgrind is not installed.'
        # if not args.enableOpt:
        #     return False, 'Valgrind needs opt builds.'
        # if args.buildWithAsan:
        #     return False, 'One should not compile with both Valgrind flags and ASan flags.'

        # if sps.isWin:
        #     return False, 'Valgrind does not work on Windows.'
        # if sps.isMac:
        #     return False, 'Valgrind does not work well with Mac OS X 10.10 Yosemite.'
        # if sps.isARMv7l and not args.enableHardFp:
        #     return False, 'libc6-dbg packages needed for Valgrind are only ' + \
        #         'available via hardfp, tested on Ubuntu on an ARM odroid board.'

    if args.runWithVg and not args.buildWithVg:
        return False, '--run-with-valgrind needs --build-with-valgrind.'

    if args.buildWithClang:
        if sps.isLinux and not args.buildWithAsan:
            return False, 'We do not really care about non-Asan clang-compiled Linux builds yet.'
        if sps.isWin:
            return False, 'Clang builds on Windows are not supported well yet.'

    if args.buildWithAsan:
        if not args.buildWithClang:
            return False, 'We should test ASan builds that are only compiled with Clang.'
        # Also check for determinism to prevent LLVM compilation from happening on releng machines,
        # since releng machines only test non-deterministic builds.
        if not args.enableMoreDeterministic:
            return False, 'We should test deterministic ASan builds.'
        if sps.isLinux:  # https://github.com/MozillaSecurity/funfuzz/issues/25
            return False, 'Linux ASan builds cannot yet submit to FuzzManager.'
        if sps.isMac:  # https://github.com/MozillaSecurity/funfuzz/issues/25
            return False, 'Mac ASan builds cannot yet submit to FuzzManager.'
        if sps.isWin:
            return False, 'Asan is not yet supported on Windows.'

    if args.enableSimulatorArm32 or args.enableSimulatorArm64:
        if sps.isARMv7l:
            return False, 'Does not make sense to run the ARM simulator on ARM hardware.'
        if sps.isWin:
            return False, 'Nobody runs the ARM simulator on Windows.'
        if args.enableSimulatorArm32 and not args.enable32:
            return False, 'The 32-bit ARM simulator builds are only for 32-bit binaries.'
        if args.enableSimulatorArm64 and args.enable32:
            return False, 'The 64-bit ARM simulator builds are only for 64-bit binaries.'
        if args.enableSimulatorArm64 and not args.enable32:
            return False, 'The 64-bit ARM simulator builds are not ready for testing yet.'

    return True, ''


def generateRandomConfigurations(parser, randomizer):
    while True:
        randomArgs = randomizer.getRandomSubset()
        if '--build-with-valgrind' in randomArgs and chance(0.95):
            randomArgs.append('--run-with-valgrind')
        buildOptions = parser.parse_args(randomArgs)
        if areArgsValid(buildOptions)[0]:
            buildOptions.buildOptionsStr = ' '.join(randomArgs)  # Used for autoBisect
            buildOptions.enableRandom = True  # This has to be true since we are randomizing...
            return buildOptions


def getRandomValidRepo(treeLocation):
    validRepos = []
    for repo in ['mozilla-central', 'mozilla-aurora', 'mozilla-esr45']:
        if os.path.isfile(sps.normExpUserPath(os.path.join(
                treeLocation, repo, '.hg', 'hgrc'))):
            validRepos.append(repo)

    # After checking if repos are valid, reduce chances that non-mozilla-central repos are chosen
    if 'mozilla-aurora' in validRepos and chance(0.5):
        validRepos.remove('mozilla-aurora')
    if 'mozilla-esr45' in validRepos and chance(0.9):
        validRepos.remove('mozilla-esr45')

    return os.path.realpath(sps.normExpUserPath(
        os.path.join(treeLocation, random.choice(validRepos))))


def main():
    print 'Here are some sample random build configurations that can be generated:'
    parser, randomizer = addParserOptions()
    buildOptions = parser.parse_args()

    if buildOptions.enableArmSimulatorObsolete:
        buildOptions.enableSimulatorArm32 = True

    for _ in range(30):
        buildOptions = generateRandomConfigurations(parser, randomizer)
        print buildOptions.buildOptionsStr

    print "\nRunning this file directly doesn't do anything, but here's our subparser help:\n"
    parseShellOptions("--help")


if __name__ == "__main__":
    main()

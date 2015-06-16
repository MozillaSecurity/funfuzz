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
    '''Adds parser options.'''
    # Where to find the source dir and compiler, patching if necessary.
    prsr = argparse.ArgumentParser(description="Usage: Don't use this directly")
    rndzer = Randomizer()

    def randomizeBool(name, fastDeviceWeight, slowDeviceWeight, **kwargs):
        '''
        Adds a randomized boolean option that defaults to False,
        and has a [weight] chance of being changed to True when using --random.
        '''
        rndzer.add(name[-1], fastDeviceWeight, slowDeviceWeight)
        prsr.add_argument(*name, action='store_true', default=False, **kwargs)

    prsr.add_argument('--random',
                      dest='enableRandom',
                      action='store_true',
                      default=False,
                      help='Chooses sensible random build options. Defaults to "%(default)s".')
    prsr.add_argument('-R', '--repoDir',
                      dest='repoDir',
                      default=sps.normExpUserPath(os.path.join('~', 'trees', 'mozilla-central')),
                      help='Sets the source repository.')
    prsr.add_argument('-P', '--patch',
                      dest='patchFile',
                      help='Define the path to a single JS patch. Ensure mq is installed.')

    # Basic spidermonkey options
    randomizeBool(['--32'], 0.5, 0.5,
                  dest='enable32',
                  help='Build 32-bit shells, but if not enabled, 64-bit shells are built.')
    randomizeBool(['--enable-debug'], 0.5, 0.5,
                  dest='enableDbg',
                  help='Build shells with --enable-debug. Defaults to "%(default)s".')
    randomizeBool(['--disable-debug'], 0, 0,  # Already default in configure.in
                  dest='disableDbg',
                  help='Build shells with --disable-debug. Defaults to "%(default)s".')
    randomizeBool(['--enable-optimize'], 0, 0,  # Already default in configure.in
                  dest='enableOpt',
                  help='Build shells with --enable-optimize. Defaults to "%(default)s".')
    randomizeBool(['--disable-optimize'], 0.1, 0.01,
                  dest='disableOpt',
                  help='Build shells with --disable-optimize. Defaults to "%(default)s".')
    randomizeBool(['--enable-profiling'], 0.5, 0,
                  dest='enableProfiling',
                  help='Build shells with --enable-profiling. Defaults to "%(default)s".')

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
    prsr.add_argument('--run-with-valgrind',
                      dest='runWithVg',
                      action='store_true',
                      default=False,
                      help='Run the shell under Valgrind. Requires --build-with-valgrind.')

    # Misc spidermonkey options
    if sps.isARMv7l:
        randomizeBool(['--enable-hardfp'], 0.1, 0.1,
                      dest='enableHardFp',
                      help='Build hardfp shells (ARM-specific setting). Defaults to "%(default)s".')
    randomizeBool(['--enable-nspr-build'], 0.5, 0.99,
                  dest='enableNsprBuild',
                  help='Build the shell using (in-tree) NSPR. This is the default on Windows. ' +
                  'On POSIX platforms, shells default to --enable-posix-nspr-emulation. ' +
                  'Using --enable-nspr-build creates a JS shell that is more like the browser. ' +
                  'Defaults to "%(default)s".')
    randomizeBool(['--enable-more-deterministic'], 0.75, 0.5,
                  dest='enableMoreDeterministic',
                  help='Build shells with --enable-more-deterministic. Defaults to "%(default)s".')
    randomizeBool(['--enable-arm-simulator'], 0.3, 0,
                  dest='enableArmSimulator',
                  help='Build shells with --enable-arm-simulator, only applicable to 32-bit shells. ' +
                  'Defaults to "%(default)s".')

    return prsr, rndzer


def parseShellOptions(inputArgs):
    """Returns a 'buildOptions' object, which is intended to be immutable."""

    prsr, rndzer = addParserOptions()
    bOpts = prsr.parse_args(inputArgs.split())

    # Ensures releng machines do not enter the if block and assumes mozilla-central always exists
    if os.path.isdir(DEFAULT_TREES_LOCATION):
        # Repositories do not get randomized if a repository is specified.
        if bOpts.repoDir is None:
            # For patch fuzzing without a specified repo, do not randomize repos, assume m-c instead
            if bOpts.enableRandom and not bOpts.patchFile:
                bOpts.repoDir = getRandomValidRepo(DEFAULT_TREES_LOCATION)
            else:
                bOpts.repoDir = os.path.realpath(sps.normExpUserPath(
                    os.path.join(DEFAULT_TREES_LOCATION, 'mozilla-central')))

        assert hgCmds.isRepoValid(bOpts.repoDir)

        if bOpts.patchFile:
            hgCmds.ensureMqEnabled()
            bOpts.patchFile = sps.normExpUserPath(bOpts.patchFile)
            assert os.path.isfile(bOpts.patchFile)

    if bOpts.enableRandom:
        bOpts = generateRandomConfigurations(prsr, rndzer)
    else:
        bOpts.buildOptionsStr = inputArgs
        valid = areArgsValid(bOpts)
        if not valid[0]:
            print 'WARNING: This set of build options is not tested well because: ' + valid[1]

    return bOpts


def computeShellType(bOpts):
    '''Returns configuration information of the shell.'''
    fileName = ['js']
    if bOpts.enableDbg:
        fileName.append('dbg')
    if bOpts.disableOpt:
        fileName.append('optDisabled')
    fileName.append('32' if bOpts.enable32 else '64')
    if bOpts.enableProfiling:
        fileName.append('prof')
    if bOpts.enableMoreDeterministic:
        fileName.append('dm')
    if bOpts.buildWithAsan:
        fileName.append('asan')
    if bOpts.buildWithVg:
        fileName.append('vg')
    if bOpts.enableNsprBuild:
        fileName.append('nsprBuild')
    if bOpts.enableArmSimulator:
        fileName.append('armSim')
    if sps.isARMv7l:
        fileName.append('armhfp' if bOpts.enableHardFp else 'armsfp')
    fileName.append('windows' if sps.isWin else platform.system().lower())
    if bOpts.patchFile:
        # We take the name before the first dot, so Windows (hopefully) does not get confused.
        fileName.append(os.path.basename(bOpts.patchFile).split('.')[0])
        # Append the patch hash, but this is not equivalent to Mercurial's hash of the patch.
        fileName.append(hashlib.sha512(file(os.path.abspath(bOpts.patchFile), 'rb').read())
                        .hexdigest()[:12])

    assert '' not in fileName, 'fileName "' + repr(fileName) + '" should not have empty elements.'
    return '-'.join(fileName)


def computeShellName(bOpts, buildRev):
    '''Returns the shell type together with the build revision.'''
    return computeShellType(bOpts) + '-' + buildRev


def areArgsValid(args):
    '''Checks to see if chosen arguments are valid.'''
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
        if not sps.isProgramInstalled('valgrind'):
            return False, 'Valgrind is not installed.'
        if not args.enableOpt:
            return False, 'Valgrind needs opt builds.'
        if args.buildWithAsan:
            return False, 'One should not compile with both Valgrind flags and ASan flags.'

        if sps.isWin:
            return False, 'Valgrind does not work on Windows.'
        if sps.isMac:
            return False, 'Valgrind does not work well with Mac OS X 10.10 Yosemite.'
        if sps.isARMv7l and not args.enableHardFp:
            return False, 'libc6-dbg packages needed for Valgrind are only ' + \
                'available via hardfp, tested on Ubuntu on an ARM odroid board.'

    if args.runWithVg and not args.buildWithVg:
        return False, '--run-with-valgrind needs --build-with-valgrind.'

    if args.buildWithAsan:
        if sps.isLinux:
            return False, 'FIXME: Figure out why compiling with Asan does not work in this harness.'
        if sps.isWin:
            return False, 'Asan is not yet supported on Windows.'

    if args.enableArmSimulator:
        if sps.isARMv7l:
            return False, 'We cannot run the ARM simulator in an ARM build.'
        if sps.isWin:
            return False, 'Nobody runs the ARM simulator on Windows.'
        if not args.enable32:  # Remove this when we have the ARM64 simulator builds
            return False, 'The ARM simulator builds are only for 32-bit binaries.'

    return True, ''


def generateRandomConfigurations(prsr, rndzer):
    while True:
        randomArgs = rndzer.getRandomSubset()
        if '--build-with-valgrind' in randomArgs and chance(0.95):
            randomArgs.append('--run-with-valgrind')
        bOpts = prsr.parse_args(randomArgs)
        if areArgsValid(bOpts)[0]:
            bOpts.buildOptionsStr = ' '.join(randomArgs)  # Used for autoBisect
            return bOpts


def getRandomValidRepo(treeLocation):
    validRepos = []
    for repo in ['mozilla-central', 'mozilla-aurora', 'mozilla-beta', 'mozilla-release',
                 'mozilla-esr31']:
        if os.path.isfile(sps.normExpUserPath(os.path.join(
                treeLocation, repo, '.hg', 'hgrc'))):
            validRepos.append(repo)

    # After checking if repos are valid, reduce chances that non-mozilla-central repos are chosen
    if 'mozilla-aurora' in validRepos and chance(0.4):
        validRepos.remove('mozilla-aurora')
    if 'mozilla-beta' in validRepos and chance(0.7):
        validRepos.remove('mozilla-beta')
    if 'mozilla-release' in validRepos and chance(0.9):
        validRepos.remove('mozilla-release')
    if 'mozilla-esr31' in validRepos and chance(0.8):
        validRepos.remove('mozilla-esr31')

    validRepos = ['mozilla-central']  # FIXME: Let's set to random configurations within m-c for now
    return os.path.realpath(sps.normExpUserPath(
        os.path.join(treeLocation, random.choice(validRepos))))


if __name__ == "__main__":
    print 'Here are some sample random build configurations that can be generated:'
    parser, randomizer = addParserOptions()
    buildOptions = parser.parse_args()

    for x in range(30):
        buildOptions = generateRandomConfigurations(parser, randomizer)
        print buildOptions.buildOptionsStr

    print "\nRunning this file directly doesn't do anything, but here's our subparser help:\n"
    parseShellOptions("--help")

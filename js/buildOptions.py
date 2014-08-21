import argparse
import os
import platform
import random
import sys
from hashlib import sha512

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
import hgCmds
import subprocesses

if platform.uname()[2] == 'XP':
    DEFAULT_MC_REPO_LOCATION = subprocesses.normExpUserPath(
        os.path.join(path0, '..', '..', 'trees', 'mozilla-central'))
else:
    DEFAULT_MC_REPO_LOCATION = subprocesses.normExpUserPath(
        os.path.join('~', 'trees', 'mozilla-central'))


def chance(p):
    return random.random() < p


class Randomizer(object):
    def __init__(self):
        self.options = []
    def add(self, name, weight):
        self.options.append({
            'name': name,
            'weight': weight
        })
    def getRandomSubset(self):
        return [o['name'] for o in self.options if chance(o['weight'])]


def addParserOptions():
    '''Adds parser options.'''
    # Where to find the source dir and compiler, patching if necessary.
    parser = argparse.ArgumentParser(description="Usage: Don't use this directly")
    randomizer = Randomizer()

    def randomizeBool(name, weight, **kwargs):
        '''
        Adds a randomized boolean option that defaults to False,
        and has a [weight] chance of being changed to True when using --random.
        '''
        randomizer.add(name[-1], weight)
        parser.add_argument(*name, action='store_true', default=False, **kwargs)

    parser.add_argument('--random',
           dest = 'enableRandom',
         action ='store_true',
        default = False,
           help = 'Chooses sensible random build options. Defaults to "%(default)s".'
    )
    # FIXME: randomise repos as well??
    parser.add_argument('-R', '--repoDir',
        dest = 'repoDir',
     default = subprocesses.normExpUserPath(os.path.join('~', 'trees', 'mozilla-central')),
        help = 'Sets the source repository. Defaults to "%(default)s".'
    )
    parser.add_argument('-P', '--patch',
        dest = 'patchFile',
        help = 'Define the path to a single JS patch. Ensure mq is installed.'
    )

    # Basic spidermonkey options
    randomizeBool(['--32'], 0.5,
        dest = 'enable32',
        help = 'Build 32-bit shells, but if not enabled, 64-bit shells are built.'
    )
    randomizeBool(['--enable-debug'], 0.5,
        dest = 'enableDbg',
        help = 'Build shells with --enable-debug. Defaults to "%(default)s".'
    )
    randomizeBool(['--disable-debug'], 0.25,
        dest = 'disableDbg',
        help = 'Build shells with --disable-debug. Defaults to "%(default)s".'
    )
    randomizeBool(['--enable-optimize'], 0.8,
        dest = 'enableOpt',
        help = 'Build shells with --enable-optimize. Defaults to "%(default)s".'
    )
    randomizeBool(['--disable-optimize'], 0.1,
        dest = 'disableOpt',
        help = 'Build shells with --disable-optimize. Defaults to "%(default)s".'
    )
    randomizeBool(['--enable-profiling'], 0.5,
        dest = 'enableProfiling',
        help = 'Build shells with --enable-profiling. Defaults to "%(default)s".'
    )

    # Memory debuggers
    randomizeBool(['--build-with-asan'], 0.3,
        dest = 'buildWithAsan',
        help = 'Build with clang AddressSanitizer support. Defaults to "%(default)s".'
    )
    randomizeBool(['--build-with-valgrind'], 0.2,
        dest = 'buildWithVg',
        help = 'Build with valgrind.h bits. Defaults to "%(default)s". ' + \
               'Requires --enable-hardfp for ARM platforms.'
    )
    # We do not use randomizeBool because we add this flag automatically if --build-with-valgrind
    # is selected.
    parser.add_argument('--run-with-valgrind',
           dest = 'runWithVg',
         action ='store_true',
        default = False,
           help = 'Run the shell under Valgrind. Requires --build-with-valgrind.'
    )

    # Misc spidermonkey options
    if subprocesses.isARMv7l:
        randomizeBool(['--enable-hardfp'], 0.5,
            dest = 'enableHardFp',
            help = 'Build hardfp shells (ARM-specific setting). Defaults to "%(default)s".'
        )
    randomizeBool(['--enable-nspr-build'], 0.5,
        dest = 'enableNsprBuild',
        help = 'Build the shell using (in-tree) NSPR. This is the default on Windows. ' + \
               'On POSIX platforms, shells default to --enable-posix-nspr-emulation. ' + \
               'Using --enable-nspr-build creates a JS shell that is more like the browser. ' + \
               'Defaults to "%(default)s".'
    )
    randomizeBool(['--enable-more-deterministic'], 0.9,
        dest = 'enableMoreDeterministic',
        help = 'Build shells with --enable-more-deterministic. Defaults to "%(default)s".'
    )
    randomizeBool(['--disable-exact-rooting'], 0.1,
        dest = 'disableExactRooting',
        help = 'Build shells with --disable-exact-rooting. Defaults to "%(default)s". ' + \
               'Implies --disable-gcgenerational.'
    )
    randomizeBool(['--disable-gcgenerational'], 0.1,
        dest = 'disableGcGenerational',
        help = 'Build shells with --disable-gcgenerational. Defaults to "%(default)s".'
    )
    randomizeBool(['--enable-arm-simulator'], 0.3,
        dest = 'enableArmSimulator',
        help = 'Build shells with --enable-arm-simulator, only applicable to 32-bit shells. ' + \
               'Defaults to "%(default)s".'
    )

    return parser, randomizer


def parseShellOptions(inputArgs):
    """Returns a 'buildOptions' object, which is intended to be immutable."""

    parser, randomizer = addParserOptions()
    buildOptions = parser.parse_args(inputArgs.split())

    # This ensures that releng machines do not enter the if block.
    if os.path.isfile(subprocesses.normExpUserPath(
            os.path.join(DEFAULT_MC_REPO_LOCATION, '.hg', 'hgrc'))):
        assert hgCmds.isRepoValid(buildOptions.repoDir)

    if buildOptions.patchFile:
        hgCmds.ensureMqEnabled()
        buildOptions.patchFile = subprocesses.normExpUserPath(buildOptions.patchFile)
        assert os.path.isfile(buildOptions.patchFile)

    if buildOptions.enableRandom:
        buildOptions = generateRandomConfigurations(parser, randomizer)
    else:
        buildOptions.buildOptionsStr = inputArgs
        valid = areArgsValid(buildOptions)
        if not valid[0]:
            print 'WARNING: This set of build options is not tested well because: ' + valid[1]

    return buildOptions


def computeShellName(buildOptions, extraIdentifier):
    """Makes a compact name that contains most of the configuration information for the shell"""
    fileName = ['js']
    if buildOptions.enableDbg:
        fileName.append('dbg')
    if buildOptions.disableDbg:
        fileName.append('dbgDisabled')
    if buildOptions.enableOpt:
        fileName.append('opt')
    if buildOptions.disableOpt:
        fileName.append('optDisabled')
    fileName.append('32' if buildOptions.enable32 else '64')
    if buildOptions.enableProfiling:
        fileName.append('prof')
    if buildOptions.enableMoreDeterministic:
        fileName.append('dm')
    if buildOptions.buildWithAsan:
        fileName.append('asan')
    if buildOptions.buildWithVg:
        fileName.append('vg')
    if buildOptions.enableNsprBuild:
        fileName.append('nsprBuild')
    if buildOptions.disableExactRooting:
        fileName.append('erDisabled')
    if buildOptions.disableGcGenerational:
        fileName.append('ggcDisabled')
    if buildOptions.enableArmSimulator:
        fileName.append('armSim')
    if subprocesses.isARMv7l:
        fileName.append('hfp' if buildOptions.enableHardFp else 'sfp')
    fileName.append('windows' if subprocesses.isWin else platform.system().lower())
    if extraIdentifier:
        fileName.append(extraIdentifier)

    if buildOptions.patchFile:
        # We take the name before the first dot, so Windows (hopefully) does not get confused.
        fileName.append(os.path.basename(buildOptions.patchFile).split('.')[0])
        # Append the patch hash, but this is not equivalent to Mercurial's hash of the patch.
        fileName.append(sha512(file(os.path.abspath(buildOptions.patchFile),
                                    'rb').read()).hexdigest()[:12])

    assert '' not in fileName, 'fileName "' + repr(fileName) + '" should not have empty elements.'
    return '-'.join(fileName)


def areArgsValid(args):
    '''Checks to see if chosen arguments are valid.'''
    if not args.enableDbg and not args.enableOpt:
        return False, 'Making a non-debug, non-optimized build would be kind of silly.'
    if subprocesses.isARMv7l and not args.enable32:
        return False, '64-bit ARM builds are not yet supported.'

    if subprocesses.isWin and (args.enable32 == subprocesses.isMozBuild64):
        return False, 'Win32 builds need the 32-bit MozillaBuild batch file and likewise the ' + \
            'corresponding 64-bit ones for Win64 builds.'

    if args.buildWithVg:
        if not subprocesses.isProgramInstalled('valgrind'):
            return False, 'Valgrind is not installed.'
        if not args.enableOpt:
            return False, 'Valgrind needs opt builds.'
        if args.buildWithAsan:
            return False, 'One should not compile with both Valgrind flags and ASan flags.'

        if subprocesses.isWin:
            return False, 'Valgrind does not work on Windows.'
        if subprocesses.isMac:
            return False, 'Valgrind does not yet work well on Mac OS X.'
        if subprocesses.isARMv7l and not args.enableHardFp:
            return False, 'libc6-dbg packages needed for Valgrind are only ' + \
                'available via hardfp, tested on Ubuntu on an ARM odroid board.'

    if args.runWithVg and not args.buildWithVg:
        return False, '--run-with-valgrind needs --build-with-valgrind.'

    if args.buildWithAsan and subprocesses.isWin:
        return False, 'Asan is not yet supported on Windows.'

    if not args.disableGcGenerational and args.disableExactRooting:
        return False, 'If exact rooting is disabled, GGC must also be disabled.'

    if args.enableArmSimulator:
        if subprocesses.isARMv7l:
            return False, 'We cannot run the ARM simulator in an ARM build.'
        if not args.enable32:  # Remove this when we have the ARM64 simulator builds
            return False, 'The ARM simulator builds are only for 32-bit binaries.'

    return True, ''


def generateRandomConfigurations(parser, randomizer):
    while True:
        randomArgs = randomizer.getRandomSubset()
        if '--build-with-valgrind' in randomArgs and chance(0.95):
            randomArgs.append('--run-with-valgrind')
        buildOptions = parser.parse_args(randomArgs)
        if areArgsValid(buildOptions)[0]:
            buildOptions.buildOptionsStr = ' '.join(randomArgs)  # Used for autoBisect
            return buildOptions


if __name__ == "__main__":
    print 'Here are some sample random build configurations that can be generated:'
    parser, randomizer = addParserOptions()
    buildOptions = parser.parse_args()

    for x in range(30):
        buildOptions = generateRandomConfigurations(parser, randomizer)
        print buildOptions.buildOptionsStr

    print "\nRunning this file directly doesn't do anything, but here's our subparser help:\n"
    parseShellOptions("--help")

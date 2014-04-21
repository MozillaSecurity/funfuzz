import os
import sys
import optparse
import platform

from hashlib import sha512

path0 = os.path.dirname(os.path.abspath(__file__))
path2 = os.path.abspath(os.path.join(path0, os.pardir, 'js'))
sys.path.append(path2)
path3 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path3)
from downloadBuild import mozPlatformDetails
import hgCmds
from subprocesses import isARMv7l, isLinux, isMac, isMozBuild64, isWin, normExpUserPath

if platform.uname()[2] == 'XP':
    DEFAULT_MC_REPO_LOCATION = normExpUserPath(os.path.join(path0, '..', '..', 'trees', 'mozilla-central'))
else:
    DEFAULT_MC_REPO_LOCATION = normExpUserPath(os.path.join('~', 'trees', 'mozilla-central'))

def parseShellOptions(inputArgs):
    """Returns a 'buildOptions' object, which is intended to be immutable."""

    usage = "Usage: Don't use this directly"
    parser = optparse.OptionParser(usage)
    # http://docs.python.org/library/optparse.html#optparse.OptionParser.disable_interspersed_args
    parser.disable_interspersed_args()

    parser.set_defaults(
        repoDir = None,
        arch = '64' if mozPlatformDetails()[2] else '32',
        compileType = 'dbg',
        enableHardFp = False,
        isThreadsafe = False,
        runWithVg = False,
        buildWithVg = False,
        buildWithAsan = False,
        enableMoreDeterministic = False,
        disableExactRooting = False,
        disableGcGenerational = False,
    )

    # Where to find the source dir and compiler, patching if necessary.
    parser.add_option('-R', '--repoDir', dest='repoDir',
                      help='Sets the source repository. Defaults to "%default".')
    parser.add_option('-P', '--patch', dest='patchFile',
                      help='Define the path to a single JS patch. Ensure mq is installed.')

    # Basic spidermonkey options
    parser.add_option('-a', '--arch', dest='arch',
                      type='choice', choices=['32', '64'],
                      help='Test computer architecture. Only accepts "32" or "64".')
    parser.add_option('-c', '--compileType', dest='compileType',
                      type='choice', choices=['dbg', 'opt'],
                      help='js shell compile type. Defaults to "%default"')

    # Memory debuggers
    parser.add_option('--build-with-asan', dest='buildWithAsan', action='store_true',
                      help='Build with clang AddressSanitizer support. Defaults to "%default".')

    parser.add_option('--build-with-valgrind', dest='buildWithVg',
                      action='store_true',
                      help='Build with valgrind.h bits. Defaults to "%default".')
    parser.add_option('--run-with-valgrind', dest='runWithVg',
                      action='store_true',
                      help='Run the shell under Valgrind.  Requires --build-with-valgrind.')

    # Misc spidermonkey options
    parser.add_option('--enable-hardfp', dest='enableHardFp',
                      action='store_true',
                      help='Build hardfp shells (ARM-specific setting). Defaults to "%default".')
    parser.add_option('--enable-threadsafe', dest='isThreadsafe', action='store_true',
                      help='Enable compilation and fuzzing of threadsafe js shell. ' + \
                           'NSPR should first be installed, see: ' + \
                           'https://developer.mozilla.org/en/NSPR_build_instructions ' + \
                           'Defaults to "%default".')
    parser.add_option('--enable-more-deterministic', dest='enableMoreDeterministic',
                      action='store_true',
                      help='Build shells with --enable-more-deterministic. Defaults to "%default".')
    parser.add_option('--disable-exact-rooting', dest='disableExactRooting',
                      action='store_true',
                      help='Build shells with --disable-exact-rooting. Defaults to "%default".' + \
                           'Implies --disable-gcgenerational.')
    parser.add_option('--disable-gcgenerational', dest='disableGcGenerational',
                      action='store_true',
                      help='Build shells with --disable-gcgenerational. Defaults to "%default".')

    (options, args) = parser.parse_args(inputArgs.split())

    # This ensures that releng machines do not enter the if block.
    if os.path.isfile(normExpUserPath(os.path.join(DEFAULT_MC_REPO_LOCATION, '.hg', 'hgrc'))):
        if options.repoDir is None:
            options.repoDir = hgCmds.getMcRepoDir()[1]
        else:  # options.repoDir is manually set.
            options.repoDir = os.path.expanduser(normExpUserPath(options.repoDir))

        if hgCmds.getRepoNameFromHgrc(options.repoDir) == '':
            raise Exception('Not a valid Mercurial repository!')

        hgCmds.destroyPyc(options.repoDir)

    options.inputArgs = inputArgs
    assert len(args) == 0

    assert options.compileType in ['opt', 'dbg']
    assert options.arch in ['32', '64']

    if options.buildWithVg:
        assert isLinux or isMac
        if isLinux and isARMv7l:
            assert options.enableHardFp, 'libc6-dbg packages needed for Valgrind are only ' + \
                'available via hardfp, tested on Ubuntu on a pandaboard.'
    if options.runWithVg:
        assert options.buildWithVg
        assert not options.buildWithAsan

    if options.buildWithAsan:
        assert not isWin, 'Asan is not yet supported on Windows.'

    if options.enableHardFp:
        assert isLinux and isARMv7l

    if options.disableExactRooting:
        options.disableGcGenerational = True

    if options.patchFile:
        hgCmds.ensureMqEnabled()
        options.patchFile = normExpUserPath(options.patchFile)
        assert os.path.isfile(options.patchFile)

    if isWin:
        assert isMozBuild64 == (options.arch == '64')

    return options


def computeShellName(options, extraIdentifier):
    """Makes a compact name that contains most of the configuration information for the shell"""
    specialParamList = []
    if options.enableMoreDeterministic:
        specialParamList.append('dm')
    if options.buildWithAsan:
        specialParamList.append('asan')
    if options.buildWithVg:
        specialParamList.append('vg')
    if options.isThreadsafe:
        specialParamList.append('ts')
    if options.disableExactRooting:
        specialParamList.append('erDisabled')
    if options.disableGcGenerational:
        specialParamList.append('ggcDisabled')
    if isARMv7l:
        if options.enableHardFp:
            specialParamList.append('hfp')
        else:
            specialParamList.append('sfp')
    specialParam = '-'.join(specialParamList)

    fileName = ['js', options.compileType, options.arch, specialParam,
                                'windows' if isWin else platform.system().lower(),
                                extraIdentifier]
    if options.patchFile:
        # We take the name before the first dot, so Windows (hopefully) does not get confused.
        fileName.append(os.path.basename(options.patchFile).split('.')[0])
        # Append the patch hash, but this is not equivalent to Mercurial's hash of the patch.
        fileName.append(sha512(file(os.path.abspath(options.patchFile), 'rb').read()).hexdigest()[:12])

    return '-'.join(x for x in fileName if x)

if __name__ == "__main__":
    print "Running this file directly doesn't do anything, but here's the help for our subparser:"
    print
    parseShellOptions("--help")

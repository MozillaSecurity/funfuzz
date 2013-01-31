import os
import sys
import optparse
import platform

path0 = os.path.dirname(os.path.abspath(__file__))
path2 = os.path.abspath(os.path.join(path0, os.pardir, 'js'))
sys.path.append(path2)
from inspectShell import constructVgCmdList, testBinary
path3 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path3)
from downloadBuild import mozPlatformDetails
from subprocesses import isWin, isMac, isLinux, normExpUserPath

def parseShellOptions(inputArgList):
    """Returns a 'buildOptions' object, which is intended to be immutable."""

    usage = 'Usage: %prog [options]'
    parser = optparse.OptionParser(usage)
    # http://docs.python.org/library/optparse.html#optparse.OptionParser.disable_interspersed_args
    parser.disable_interspersed_args()

    parser.set_defaults(
        arch = '64' if mozPlatformDetails()[2] else '32',
        compileType = 'dbg',
        isThreadsafe = False,
        runWithVg = False,
        buildWithVg = False,
        buildWithAsan = False,
        llvmRootSrcDir = normExpUserPath('~/llvm'),
        enableMoreDeterministic = False,
        enableRootAnalysis = False,
    )

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
    parser.add_option('--llvm-root', dest='llvmRootSrcDir',
                      help='Specify the LLVM root source dir (for clang). Defaults to "%default".')

    parser.add_option('--build-with-valgrind', dest='buildWithVg',
                      action='store_true',
                      help='Build with valgrind.h bits. Defaults to "%default".')
    parser.add_option('--run-with-valgrind', dest='runWithVg',
                      action='store_true',
                      help='Run the shell under Valgrind.  Requires --build-with-valgrind.')

    # Misc spidermonkey options
    parser.add_option('--enable-threadsafe', dest='isThreadsafe', action='store_true',
                      help='Enable compilation and fuzzing of threadsafe js shell. ' + \
                           'NSPR should first be installed, see: ' + \
                           'https://developer.mozilla.org/en/NSPR_build_instructions ' + \
                           'Defaults to "%default".')
    parser.add_option('--enable-more-deterministic', dest='enableMoreDeterministic',
                      action='store_true',
                      help='Build shells with --enable-more-deterministic. Defaults to "%default".')
    parser.add_option('--enable-root-analysis', dest='enableRootAnalysis',
                      action='store_true',
                      help='Build shells with --enable-root-analysis. Defaults to "%default".')

    (options, args) = parser.parse_args(inputArgList.split())
    options.inputArgList = inputArgList
    assert len(args) == 0

    assert options.compileType in ['opt', 'dbg']
    assert options.arch in ['32', '64']

    if options.buildWithVg:
        assert (isLinux and (os.uname()[4] != 'armv7l')) or isMac
    if options.runWithVg:
        assert options.buildWithVg
        assert not options.buildWithAsan

    if isWin:
        assert ('x64' in os.environ['MOZ_TOOLS'].split(os.sep)[-1]) == (options.arch == '64')

    return options


def computeShellName(options, extraIdentifier):
    """Makes a compact name that contains most of the configuration information for the shell"""
    specialParamList = []
    if options.enableMoreDeterministic:
        specialParamList.append('dm')
    if options.enableRootAnalysis:
        specialParamList.append('ra')
    if options.buildWithAsan:
        specialParamList.append('asan')
    if options.buildWithVg:
        specialParamList.append('vg')
    if options.isThreadsafe:
        specialParamList.append('ts')
    specialParam = '-'.join(specialParamList)
    return '-'.join(x for x in ['js', options.compileType, options.arch, specialParam,
                                'windows' if isWin else platform.system().lower(),
                                extraIdentifier] if x)

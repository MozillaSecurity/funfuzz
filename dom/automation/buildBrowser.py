import os
import sys
import optparse
import platform
import time
import copy
import subprocess
import shutil
import tempfile

path0 = os.path.dirname(os.path.abspath(__file__))
path3 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path3)
from downloadBuild import mozPlatformDetails
from subprocesses import isWin, isWin64, isMac, isLinux, normExpUserPath
from hgCmds import getMcRepoDir, getRepoNameFromHgrc, destroyPyc

def parseOptions(inputArgs):
    """Returns a 'buildOptions' object, which is intended to be immutable."""

    usage = "Usage: Don't use this directly"
    parser = optparse.OptionParser(usage)
    # http://docs.python.org/library/optparse.html#optparse.OptionParser.disable_interspersed_args
    parser.disable_interspersed_args()

    parser.set_defaults(
        repoDir = getMcRepoDir()[1],
        objDir = None,
        mozconfig = None
    )

    parser.add_option('-R', '--repoDir', dest='repoDir',
                      help='Sets the source repository. Defaults to "%default".')
    parser.add_option('-o', '--objDir', dest='objDir',
                      help='The obj dir that will be created by the given mozconfig. Will be blown away multiple times.')
    parser.add_option('-c', '--mozconfig', dest='mozconfig',
                      help='A mozconfig file.')

    (options, args) = parser.parse_args(inputArgs.split())

    # All are required for now
    assert options.objDir
    assert options.repoDir
    assert options.mozconfig

    options.objDir = os.path.expanduser(options.objDir)
    options.repoDir = os.path.expanduser(options.repoDir)
    options.mozconfig = os.path.expanduser(options.mozconfig)

    assert os.path.exists(options.repoDir)
    assert os.path.exists(options.mozconfig)

    return options


def makeTestRev(options):
    env = copy.deepcopy(os.environ)
    env['MOZCONFIG'] = options.browserOptions.mozconfig

    srcDir = options.browserOptions.repoDir
    objDir = options.browserOptions.objDir

    def testRev(rev):
        print "Updating to " + rev + "..."
        subprocess.check_call(['hg', '-R', srcDir, 'update', '-r', rev])
        destroyPyc(srcDir)

        print "Compiling..."
        if os.path.exists(objDir):
            shutil.rmtree(objDir)

        compileOutput = tempfile.NamedTemporaryFile(delete=False)
        compileOutputFn = compileOutput.name
        rv = subprocess.call(['make', '-C', srcDir, '-f', 'client.mk'], env=env, stdout=compileOutput.file, stderr=subprocess.STDOUT)
        compileOutput.close()
        # XXX Wrong
        if rv != 0 or not (os.path.exists(os.path.join(objDir, 'dist', 'NightlyDebug.app', 'Contents', 'MacOS', 'firefox')) or os.path.exists(os.path.join(objDir, 'dist', 'Nightly.app', 'Contents', 'MacOS', 'firefox'))):
            print "Compilation failed: " + compileOutputFn
            return (options.compilationFailedLabel, "compilation failed")
        os.remove(compileOutputFn)

        print "Testing..."
        ans = options.testAndLabel(objDir, rev)
        time.sleep(8)
        return ans

    return testRev

if __name__ == "__main__":
    print "Running this file directly doesn't do anything, but here's the help for our subparser:"
    print
    parseShellOptions("--help")

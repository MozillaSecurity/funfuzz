#!/usr/bin/env python

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
path3 = os.path.abspath(os.path.join(path0, os.pardir, os.pardir, 'util'))
sys.path.append(path3)
from downloadBuild import mozPlatformDetails
from subprocesses import isWin, isWin64, isMac, isLinux, normExpUserPath
from hgCmds import getMcRepoDir, getRepoNameFromHgrc, destroyPyc

def parseOptions(inputArgs):
    """Returns a 'buildOptions' object, which is intended to be immutable."""

    parser = optparse.OptionParser()
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
                      help='The obj dir that will be created by the given mozconfig. May get clobbered.')
    parser.add_option('-c', '--mozconfig', dest='mozconfig',
                      help='A mozconfig file.')

    (options, args) = parser.parse_args(inputArgs)

    if len(args) > 0:
        parser.print_help()
        raise Exception("buildBrowser.py: extra arguments")

    # All are required for now
    if not (options.objDir and options.repoDir and options.mozconfig):
        print "buildBrowser requires you to specify a repoDir, objDir, and mozconfig"
        parser.print_help()
        raise Exception("buildBrowser.py: usage")

    options.objDir = os.path.expanduser(options.objDir)
    options.repoDir = os.path.expanduser(options.repoDir)
    options.mozconfig = os.path.expanduser(options.mozconfig)

    assert os.path.exists(options.repoDir)
    assert os.path.exists(options.mozconfig)

    return options


def tryCompiling(options):
    env = copy.deepcopy(os.environ)
    env['MOZCONFIG'] = options.mozconfig

    compileOutput = tempfile.NamedTemporaryFile(delete=False)
    compileOutputFn = compileOutput.name
    print "Compiling (details in " + compileOutputFn + ")..."
    rv = subprocess.call(['make', '-C', options.repoDir, '-f', 'client.mk'], env=env, stdout=compileOutput.file, stderr=subprocess.STDOUT)
    compileOutput.close()
    if rv != 0:
        print "Compilation failed"
        time.sleep(8)
        shutil.rmtree(objDir)
        os.remove(compileOutputFn)
        return False
    else:
        os.remove(compileOutputFn)
        return True


# For autoBisect
def makeTestRev(options):
    srcDir = options.browserOptions.repoDir
    objDir = options.browserOptions.objDir

    def testRev(rev):
        print "Updating to " + rev + "..."
        subprocess.check_call(['hg', '-R', srcDir, 'update', '-r', rev])
        destroyPyc(srcDir)

        if os.path.exists(objDir):
            print "Clobbering..."
            # We don't trust the clobberer while bisecting
            shutil.rmtree(objDir)

        if not tryCompiling(options.browserOptions):
            return (options.compilationFailedLabel, "compilation failed")

        print "Testing..."
        assert os.path.exists(objDir)
        ans = options.testAndLabel(objDir, rev)
        time.sleep(8)
        return ans

    return testRev

if __name__ == "__main__":
    print tryCompiling(parseOptions(sys.argv[1:]))

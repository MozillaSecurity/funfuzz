#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import with_statement

import os
import subprocess
import sys
from optparse import OptionParser

import buildOptions

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
path2 = os.path.abspath(os.path.join(path0, os.pardir))
sys.path.append(path2)
from bot import localCompileFuzzJsShell, machineTimeoutDefaults
from subprocesses import normExpUserPath


def parseOptions():
    usage = 'Usage: %prog [options]'
    parser = OptionParser(usage)

    parser.set_defaults(
        disableCompareJit = False,
        disableRndFlags = False,
        noStart = False,
        timeout = 0,
        buildOptions = ""
    )

    parser.add_option('--disable-comparejit', dest='disableCompareJit', action='store_true',
                      help='Disable comparejit fuzzing.')
    parser.add_option('--disable-random-flags', dest='disableRndFlags', action='store_true',
                      help='Disable random flag fuzzing.')
    parser.add_option('--nostart', dest='noStart', action='store_true',
                      help='Compile shells only, do not start fuzzing.')

    # Specify how the shell will be built.
    # See buildOptions.py for details.
    parser.add_option('-b', '--build',
                      dest='buildOptions',
                      help='Specify build options, e.g. -b "-c opt --arch=32" (python buildOptions.py --help)')

    parser.add_option('-t', '--timeout', type='int', dest='timeout',
                      help='Sets the timeout for loopjsfunfuzz.py. ' + \
                           'Defaults to taking into account the speed of the computer and ' + \
                           'debugger (if any).')

    parser.add_option('-p', '--set-patchDir', dest='patchDir',
                      #help='Define the path to a single patch or to a directory containing mq ' + \
                      #     'patches. Must have a "series" file present, containing the names ' + \
                      #     'of the patches, the first patch required at the bottom of the list.')
                      help='Define the path to a single patch. Multiple patches are not yet ' + \
                           'supported.')

    options, args = parser.parse_args()

    if options.patchDir:
        options.patchDir = normExpUserPath(options.patchDir)

    if not options.disableCompareJit:
        options.buildOptions += " --enable-more-deterministic"

    options.buildOptions = buildOptions.parseShellOptions(options.buildOptions)

    options.timeout = options.timeout or machineTimeoutDefaults(options)

    return options

def main():
    options = parseOptions()

    fuzzShell, cList = localCompileFuzzJsShell(options)
    startDir = fuzzShell.getBaseTempDir()

    if options.noStart:
        print 'Exiting, --nostart is set.'
        sys.exit(0)
    else:
        assert os.path.exists(normExpUserPath(os.path.join(path0, 'jsfunfuzz.js'))), \
            'jsfunfuzz.js should be in the same location for the fuzzing harness to work.'

    # Commands to simulate bash's `tee`.
    tee = subprocess.Popen(['tee', 'log-jsfunfuzz.txt'], stdin=subprocess.PIPE, cwd=startDir)

    # Start fuzzing the newly compiled builds.
    subprocess.call(cList, stdout=tee.stdin, cwd=startDir)


# Run main when run as a script, this line means it will not be run as a module.
if __name__ == '__main__':
    main()

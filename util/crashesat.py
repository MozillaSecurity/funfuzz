#!/usr/bin/env python
# coding=utf-8
# pylint: disable=import-error,invalid-name,missing-docstring,no-else-return,wrong-import-position
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import absolute_import, print_function

import os
import sys
from optparse import OptionParser  # pylint: disable=deprecated-module

import subprocesses as sps

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, os.pardir, 'lithium', 'interestingness'))
sys.path.append(path1)
import timedRun
import fileIngredients


def parseOptions(arguments):
    parser = OptionParser()
    parser.disable_interspersed_args()
    parser.add_option('-r', '--regex', action='store_true', dest='useRegex',
                      default=False,
                      help='Allow search for regular expressions instead of strings.')
    parser.add_option('-s', '--sig', action='store', dest='sig',
                      default='',
                      help='Match this crash signature. Defaults to "%default".')
    parser.add_option('-t', '--timeout', type='int', action='store', dest='condTimeout',
                      default=120,
                      help='Optionally set the timeout. Defaults to "%default" seconds.')

    options, args = parser.parse_args(arguments)

    return options.useRegex, options.sig, options.condTimeout, args


def interesting(cliArgs, tempPrefix):
    (regexEnabled, crashSig, timeout, args) = parseOptions(cliArgs)

    # Examine stack for crash signature, this is needed if crashSig is specified.
    runinfo = timedRun.timed_run(args, timeout, tempPrefix)
    if runinfo.sta == timedRun.CRASHED:
        sps.grabCrashLog(args[0], runinfo.pid, tempPrefix, True)

    timeString = " (%.3f seconds)" % runinfo.elapsedtime

    crashLogName = tempPrefix + "-crash.txt"

    if runinfo.sta == timedRun.CRASHED:
        if os.path.exists(crashLogName):
            # When using this script, remember to escape characters, e.g. "\(" instead of "(" !
            found, _foundSig = fileIngredients.fileContains(crashLogName, crashSig, regexEnabled)
            if found:
                print("Exit status: %s%s" % (runinfo.msg, timeString))
                return True
            else:
                print("[Uninteresting] It crashed somewhere else!%s" % timeString)
                return False
        else:
            print("[Uninteresting] It appeared to crash, but no crash log was found?%s" % timeString)
            return False
    else:
        print("[Uninteresting] It didn't crash.%s" % timeString)
        return False

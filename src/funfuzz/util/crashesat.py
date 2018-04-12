# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Lithium's "crashesat" interestingness test to assess whether a binary crashes at a desired location.

Not merged into Lithium, unsure if this still works for now. Still relies on grabCrashLog.
"""

from __future__ import absolute_import, print_function

import os
from optparse import OptionParser  # pylint: disable=deprecated-module

import lithium.interestingness.timed_run as timed_run
from lithium.interestingness.utils import file_contains

from . import subprocesses as sps


def parse_options(arguments):  # pylint: disable=missing-docstring,missing-return-doc,missing-return-type-doc
    parser = OptionParser()
    parser.disable_interspersed_args()
    parser.add_option("-r", "--regex", action="store_true", dest="useRegex",
                      default=False,
                      help="Allow search for regular expressions instead of strings.")
    parser.add_option("-s", "--sig", action="store", dest="sig",
                      default="",
                      help='Match this crash signature. Defaults to "%default".')
    parser.add_option("-t", "--timeout", type="int", action="store", dest="condTimeout",
                      default=120,
                      help='Optionally set the timeout. Defaults to "%default" seconds.')

    options, args = parser.parse_args(arguments)

    return options.useRegex, options.sig, options.condTimeout, args


def interesting(cli_args, temp_prefix):  # pylint: disable=missing-docstring,missing-return-doc,missing-return-type-doc
    (regex_enabled, crash_sig, timeout, args) = parse_options(cli_args)

    # Examine stack for crash signature, this is needed if crash_sig is specified.
    runinfo = timed_run.timed_run(args, timeout, temp_prefix)
    if runinfo.sta == timed_run.CRASHED:
        sps.grabCrashLog(args[0], runinfo.pid, temp_prefix, True)

    time_str = " (%.3f seconds)" % runinfo.elapsedtime

    crash_log = temp_prefix + "-crash.txt"

    if runinfo.sta == timed_run.CRASHED:
        if os.path.exists(crash_log):
            # When using this script, remember to escape characters, e.g. "\(" instead of "(" !
            found, _found_sig = file_contains(crash_log, crash_sig, regex_enabled)
            if found:
                print("Exit status: %s%s" % (runinfo.msg, time_str))
                return True
            print("[Uninteresting] It crashed somewhere else!" + time_str)
            return False
        print("[Uninteresting] It appeared to crash, but no crash log was found?" + time_str)
        return False
    print("[Uninteresting] It didn't crash." + time_str)
    return False

# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Lithium's "crashesat" interestingness test to assess whether a binary crashes with a possibly-desired signature on
the stack.

Not merged into Lithium as it still relies on grabCrashLog.
"""

from __future__ import absolute_import

import argparse
import logging
import sys

import lithium.interestingness.timed_run as timed_run
from lithium.interestingness.utils import file_contains

from . import subprocesses as sps

if sys.version_info.major == 2:
    from pathlib2 import Path
else:
    from pathlib import Path  # pylint: disable=import-error


def interesting(cli_args, temp_prefix):
    """Interesting if the binary crashes with a possibly-desired signature on the stack.

    Args:
        cli_args (list): List of input arguments.
        temp_prefix (str): Temporary directory prefix, e.g. tmp1/1 or tmp4/1

    Returns:
        bool: True if the intended signature shows up on the stack, False otherwise.
    """
    parser = argparse.ArgumentParser(prog="crashesat",
                                     usage="python -m lithium %(prog)s [options] binary [flags] testcase.ext")
    parser.add_argument("-r", "--regex", action="store_true", default=False,
                        help="Allow search for regular expressions instead of strings.")
    parser.add_argument("-s", "--sig", default="", type=str,
                        help="Match this crash signature. Defaults to '%default'.")
    parser.add_argument("-t", "--timeout", default=120, type=int,
                        help="Optionally set the timeout. Defaults to '%default' seconds.")
    parser.add_argument("cmd_with_flags", nargs=argparse.REMAINDER)
    args = parser.parse_args(cli_args)

    log = logging.getLogger(__name__)

    # Examine stack for crash signature, this is needed if args.sig is specified.
    runinfo = timed_run.timed_run(args.cmd_with_flags, args.timeout, temp_prefix)
    if runinfo.sta == timed_run.CRASHED:
        sps.grabCrashLog(args.cmd_with_flags[0], runinfo.pid, temp_prefix, True)

    crash_log = Path(temp_prefix + "-crash.txt")
    time_str = " (%.3f seconds)" % runinfo.elapsedtime

    if runinfo.sta == timed_run.CRASHED:
        if crash_log.resolve().is_file():  # pylint: disable=no-member
            # When using this script, remember to escape characters, e.g. "\(" instead of "(" !
            if file_contains(str(crash_log), args.sig, args.regex)[0]:
                log.info("Exit status: %s%s", runinfo.msg, time_str)
                return True
            log.info("[Uninteresting] It crashed somewhere else!%s", time_str)
            return False
        log.info("[Uninteresting] It appeared to crash, but no crash log was found?%s", time_str)
        return False
    log.info("[Uninteresting] It didn't crash.%s", time_str)
    return False

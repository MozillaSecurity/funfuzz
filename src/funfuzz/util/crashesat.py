# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Lithium's "crashesat" interestingness test to assess whether a binary crashes with a possibly-desired signature on
the stack.

Not merged into Lithium as it still relies on grab_crash_log.
"""

import argparse
import logging
from pathlib import Path

import lithium.interestingness.timed_run as timedrun
from lithium.interestingness.utils import file_contains

from . import os_ops


def interesting(cli_args, temp_prefix):
    """Interesting if the binary crashes with a possibly-desired signature on the stack.

    Args:
        cli_args (list): List of input arguments.
        temp_prefix (str): Temporary directory prefix, e.g. tmp1/1 or tmp4/1

    Returns:
        bool: True if the intended signature shows up on the stack, False otherwise.
    """
    parser = argparse.ArgumentParser(prog="crashesat",
                                     usage="python3 -m lithium %(prog)s [options] binary [flags] testcase.ext")
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
    runinfo = timedrun.timed_run(args.cmd_with_flags, args.timeout, temp_prefix)
    if runinfo.sta == timedrun.CRASHED:
        os_ops.grab_crash_log(Path(args.cmd_with_flags[0]), runinfo.pid, Path(temp_prefix), True)

    crash_log = Path(f"{temp_prefix}-crash.txt")
    time_str = f" ({runinfo.elapsedtime:.3f} seconds)"

    if runinfo.sta == timedrun.CRASHED:
        if crash_log.resolve().is_file():
            # When using this script, remember to escape characters, e.g. "\(" instead of "(" !
            if file_contains(str(crash_log), args.sig.encode("utf-8"), args.regex)[0]:
                log.info("Exit status: %s%s", runinfo.msg, time_str)
                return True
            log.info("[Uninteresting] It crashed somewhere else!%s", time_str)
            return False
        log.info("[Uninteresting] It appeared to crash, but no crash log was found?%s", time_str)
        return False
    log.info("[Uninteresting] It didn't crash.%s", time_str)
    return False

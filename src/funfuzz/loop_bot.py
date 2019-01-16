# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Loop of { update repos, call bot } to allow things to run unattended
All command-line options are passed through to bot

This script used to update funfuzz itself (when run as scripts, no longer supported)
so it uses subprocess.run() rather than import

Config-ish bits should move to bot, OR move into a config file,
OR this file should subprocess-run ITSELF rather than using a while loop.
"""

import subprocess
import sys
import time

from .util.logging_helpers import get_logger

LOG_LOOP_BOT = get_logger(__name__)


def loop_seq(cmd_seq, wait_time):  # pylint: disable=missing-param-doc,missing-type-doc
    """Call a sequence of commands in a loop.
    If any fails, sleep(wait_time) and go back to the beginning of the sequence."""
    i = 0
    while True:
        i += 1
        LOG_LOOP_BOT.info("localLoop #%s!", i)
        for cmd in cmd_seq:
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as ex:
                LOG_LOOP_BOT.warning("Something went wrong when calling: %r", cmd.rstrip())
                LOG_LOOP_BOT.warning("%r", ex)
                import traceback
                LOG_LOOP_BOT.warning(traceback.format_exc())
                LOG_LOOP_BOT.info("Waiting %s seconds...", wait_time)
                time.sleep(wait_time)
                break


def main():  # pylint: disable=missing-docstring
    loop_seq([
        [sys.executable, "-u", "-m", "funfuzz.util.repos_update"],
        [sys.executable, "-u", "-m", "funfuzz.bot"] + [str(x) for x in sys.argv[1:]],
    ], 60)


if __name__ == "__main__":
    main()

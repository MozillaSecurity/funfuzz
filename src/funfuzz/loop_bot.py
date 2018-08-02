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

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import logging
import os
import sys
import time

if sys.version_info.major == 2 and os.name == "posix":
    import logging_tz  # pylint: disable=import-error
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess

FUNFUZZ_LOG = logging.getLogger("funfuzz")
FUNFUZZ_LOG.setLevel(logging.DEBUG)
LOG_HANDLER = logging.StreamHandler()
if sys.version_info.major == 2:
    LOG_FORMATTER = logging_tz.LocalFormatter(datefmt="[%Y-%m-%d %H:%M:%S%z]",
                                              fmt="%(asctime)s %(name)s %(levelname)-8s %(message)s")
else:
    LOG_FORMATTER = logging.Formatter(datefmt="[%Y-%m-%d %H:%M:%S%z]",
                                      fmt="%(asctime)s %(name)s %(levelname)-8s %(message)s")
LOG_HANDLER.setFormatter(LOG_FORMATTER)
FUNFUZZ_LOG.addHandler(LOG_HANDLER)


def loop_seq(cmd_seq, wait_time):  # pylint: disable=missing-param-doc,missing-type-doc
    """Call a sequence of commands in a loop.
    If any fails, sleep(wait_time) and go back to the beginning of the sequence."""
    i = 0
    while True:
        i += 1
        FUNFUZZ_LOG.info("localLoop #%d!", i)
        for cmd in cmd_seq:
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as ex:
                FUNFUZZ_LOG.warning("Something went wrong when calling: %r", cmd.rstrip())
                FUNFUZZ_LOG.warning("%r", ex)
                import traceback
                FUNFUZZ_LOG.warning(traceback.format_exc())
                FUNFUZZ_LOG.info("Waiting %d seconds...", wait_time)
                time.sleep(wait_time)
                break


def main():  # pylint: disable=missing-docstring
    loop_seq([
        [sys.executable, "-u", "-m", "funfuzz.util.repos_update"],
        [sys.executable, "-u", "-m", "funfuzz.bot"] + [str(x) for x in sys.argv[1:]],
    ], 60)


if __name__ == "__main__":
    main()

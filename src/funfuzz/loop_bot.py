# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Loop of { update repos, call bot } to allow things to run unattended
All command-line options are passed through to bot

Since this script updates the fuzzing repo, it should be very simple, and use subprocess.call() rather than import

Config-ish bits should move to bot, OR move into a config file,
OR this file should subprocess-call ITSELF rather than using a while loop.
"""

from __future__ import absolute_import, print_function, unicode_literals

import sys
import subprocess
import time


def loop_seq(cmd_seq, wait_time):  # pylint: disable=missing-param-doc,missing-type-doc
    """Call a sequence of commands in a loop.
    If any fails, sleep(wait_time) and go back to the beginning of the sequence."""
    i = 0
    while True:
        i += 1
        print("localLoop #%d!" % i)
        for cmd in cmd_seq:
            try:
                subprocess.check_call(cmd)
            except subprocess.CalledProcessError as ex:
                print("Something went wrong when calling: %r" % (cmd,))
                print("%r" % (ex,))
                import traceback
                print(traceback.format_exc())
                print("Waiting %d seconds..." % wait_time)
                time.sleep(wait_time)
                break


def main():  # pylint: disable=missing-docstring
    loop_seq([
        [sys.executable, "-u", "-m", "funfuzz.util.repos_update"],
        [sys.executable, "-u", "-m", "funfuzz.bot"] + sys.argv[1:]
    ], 60)


if __name__ == "__main__":
    main()

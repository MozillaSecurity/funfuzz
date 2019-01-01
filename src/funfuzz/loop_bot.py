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


def loop_seq(cmd_seq, wait_time):  # pylint: disable=missing-param-doc,missing-type-doc
    """Call a sequence of commands in a loop.
    If any fails, sleep(wait_time) and go back to the beginning of the sequence."""
    i = 0
    while True:
        i += 1
        print(f"localLoop #{i}!")
        for cmd in cmd_seq:
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as ex:
                print(f"Something went wrong when calling: {cmd!r}")
                print(f"{ex!r}")
                import traceback
                print(traceback.format_exc())
                print(f"Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                break


def main():  # pylint: disable=missing-docstring
    loop_seq([
        [sys.executable, "-u", "-m", "funfuzz.util.repos_update"],
        [sys.executable, "-u", "-m", "funfuzz.bot"] + [str(x) for x in sys.argv[1:]],
    ], 60)


if __name__ == "__main__":
    main()

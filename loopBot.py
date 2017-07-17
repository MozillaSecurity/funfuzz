#!/usr/bin/env python
# coding=utf-8
# pylint: disable=invalid-name,line-too-long,missing-docstring
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Loop of { update repos, call bot.py } to allow things to run unattended
# All command-line options are passed through to bot.py

# Since this script updates the fuzzing repo, it should be very simple, and use subprocess.call() rather than import

from __future__ import absolute_import, print_function

import os
import sys
import subprocess
import time

path0 = os.path.dirname(os.path.abspath(__file__))

# Config-ish bits should move to bot.py, OR move into a config file, OR this file should subprocess-call ITSELF rather than using a while loop.


def loopSequence(cmdSequence, waitTime):
    """Call a sequence of commands in a loop. If any fails, sleep(waitTime) and go back to the beginning of the sequence."""
    i = 0
    while True:
        i += 1
        print("localLoop #%d!" % i)
        for cmd in cmdSequence:
            try:
                subprocess.check_call(cmd)
            except subprocess.CalledProcessError as e:
                print("Something went wrong when calling: %r" % (cmd,))
                print("%r" % (e,))
                import traceback
                print(traceback.format_exc())
                print("Waiting %d seconds..." % waitTime)
                time.sleep(waitTime)
                break


def main():
    loopSequence([
        [sys.executable, "-u", os.path.join(path0, 'util', 'reposUpdate.py')],
        [sys.executable, "-u", os.path.join(path0, 'bot.py')] + sys.argv[1:]
    ], 60)


if __name__ == "__main__":
    main()

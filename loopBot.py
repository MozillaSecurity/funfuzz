#!/usr/bin/env python

# Loop of { update repos, call bot.py } to allow things to run unattended
# All command-line options are passed through to bot.py (unless you use --dom-defaults)

# Since this script updates the fuzzing repo, it should be very simple, and use subprocess.call() rather than import

import os
import sys
import subprocess
import time

path0 = os.path.dirname(os.path.abspath(__file__))

# Config-ish bits should move to bot.py, OR move into a config file, OR this file should subprocess-call ITSELF rather than using a while loop.


def buildOptionsASan():
    mozconfig = os.path.expanduser("~/funfuzz/dom/mozconfig/mozconfig-asan")
    srcdir = os.path.expanduser("~/trees/mozilla-central/")
    objdir = srcdir + "obj-firefox-asan/"
    return " ".join(["--mozconfig", mozconfig, "--repoDir", srcdir, "--objDir", objdir])


def botArgs():
    if sys.argv[1:] == ['--dom-defaults']:
        return ["--test-type=dom", "--target-time=43200", "--use-treeherder-builds"]
    if sys.argv[1:] == ['--dom-asan']:
        return ["--test-type=dom", "--target-time=43200", "--build-options", buildOptionsASan()]
    return sys.argv[1:]


def loopSequence(cmdSequence, waitTime):
    """Call a sequence of commands in a loop. If any fails, sleep(waitTime) and go back to the beginning of the sequence."""
    i = 0
    while True:
        i += 1
        print "localLoop #%d!" % i
        for cmd in cmdSequence:
            try:
                subprocess.check_call(cmd)
            except subprocess.CalledProcessError as e:
                print "Something went wrong when calling: " + repr(cmd)
                print repr(e)
                import traceback
                print traceback.format_exc()
                print "Waiting %d seconds..." % waitTime
                time.sleep(waitTime)
                break


def main():
    loopSequence([
        [sys.executable, "-u", os.path.join(path0, 'util', 'reposUpdate.py')],
        [sys.executable, "-u", os.path.join(path0, 'bot.py')] + botArgs()
    ], 60)

if __name__ == "__main__":
    main()

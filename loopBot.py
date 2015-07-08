#!/usr/bin/env python

# Loop of { update repos, call bot.py } to allow things to run unattended
# All command-line options are passed through to bot.py (unless you use --dom-defaults)

# Since this script updates the fuzzing repo, it should be very simple, and use subprocess.call() rather than import

import os
import sys
import platform
import subprocess
import time

path0 = os.path.dirname(os.path.abspath(__file__))

# This junk should be moved to bot.py, OR moved into a config file, OR this file should subprocess-call ITSELF rather than using a while loop.
def buildOptionsASan():
    mozconfig = os.path.expanduser("~/funfuzz/dom/mozconfig/mozconfig-asan")
    srcdir = os.path.expanduser("~/trees/mozilla-central/")
    objdir = srcdir + "obj-firefox-asan/"
    return " ".join(["--mozconfig", mozconfig, "--repoDir", srcdir, "--objDir", objdir])
def domDefaults():
    botArgs = ["--test-type=dom", "--target-time=43200"]
    scl = platform.uname()[1].startswith("fuzzer-") # e.g. "fuzzer-linux5.sec.scl3.mozilla.com" or just "fuzzer-win1"
    if scl:
        botArgs.extend(["--remote-host", "jruderman@fuzzer-linux5.sec.scl3.mozilla.com", "--basedir", "/home/jruderman/scl-fuzz-results/"])
    if (platform.system() == "Linux" and i % 2 == 1) or (platform.system() == "Darwin" and not scl):
        botArgs.extend(["--build-options", buildOptionsASan()])
    print(repr(botArgs))
    return botArgs
def botArgs():
    if sys.argv[1:] == ['--dom-defaults']:
        return domDefaults()
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

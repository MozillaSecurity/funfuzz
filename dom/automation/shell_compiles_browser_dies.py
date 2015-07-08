#!/usr/bin/env python

import os
import subprocess
import sys

p0 = os.path.dirname(os.path.abspath(__file__))
p1 = os.path.abspath(os.path.join(p0, os.pardir, os.pardir, os.pardir, 'lithium', 'interestingness'))
sys.path.append(p1)
import timedRun

# usage: put the js in a separate file from html.  give the js filename to lithium as --testcase *and* the second parameter to this shell_compiles_browser_dies.
# for example:
# ./lithium.py --testcase=c.js shell_compiles_browser_dies.py 120 c.js ~/central/debug-obj/dist/MinefieldDebug.app/Contents/MacOS/firefox-bin uses-c.html

jsshell = os.path.expanduser("~/tracemonkey/js/src/debug/js")

def interesting(args, tempPrefix):
    timeout = int(args[0])
    returncode = subprocess.call([jsshell, "-c", args[1]], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if returncode != 0:
        print "JS didn't compile, skipping browser test"
        return False
    wantStack = False  # We do not care about the stack when using this interestingness test.
    runinfo = timedRun.timed_run(args[2:], timeout, tempPrefix, wantStack)
    print "Exit status: %s (%.3f seconds)" % (runinfo.msg, runinfo.elapsedtime)
    return runinfo.sta == timedRun.CRASHED or runinfo.sta == timedRun.ABNORMAL

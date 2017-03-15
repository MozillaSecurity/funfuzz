#!/usr/bin/env python

from __future__ import absolute_import

import os
import sys
import shutil
from optparse import OptionParser

oldcwd = os.getcwd()


def removeDirIfExists(d):
    if os.path.exists(d):
        shutil.rmtree(d, ignore_errors=True)


def runBrowser():
    parser = OptionParser()
    # we want to pass down everything from automation.__all__
    parser.add_option("--valgrind",
                      action="store_true", dest="valgrind",
                      default=False,
                      help="use valgrind with the options given in --vgargs")
    parser.add_option("--vgargs",
                      action="store", dest="vgargs",
                      default=None,
                      help="space-separated arguments to give to valgrind")
    parser.add_option("--symbols-dir",
                      action="store", dest="symbolsDir",
                      default=None)
    parser.add_option("--leak-log-file",
                      action="store", dest="leakLogFile",
                      default=None)
    parser.add_option("--background",
                      action="store_true", dest="background",
                      default=False)
    options, args = parser.parse_args(sys.argv)

    reftestScriptDir = args[1]
    utilityDir = args[2]
    profileDir = args[3]
    url = args[4]

    sys.path.append(reftestScriptDir)
    sys.path.append(os.path.join(reftestScriptDir, "..", "mozbase", "mozinfo"))
    sys.path.append(os.path.join(reftestScriptDir, "..", "mozbase", "mozfile"))
    try:
        from automation import Automation
    except ImportError:
        # The first time running from a local objdir, I get "ImportError: No module named mozcrash".
        # The correct fix is to use virtualenv: https://bugzilla.mozilla.org/show_bug.cgi?id=903616#c12
        # For now, just try again.
        from automation import Automation

    automation = Automation()

    theapp = os.path.join(reftestScriptDir, automation.DEFAULT_APP)
    if not os.path.exists(theapp):
        print "RUNBROWSER ERROR | runbrowser.py | Application %s doesn't exist." % theapp
        sys.exit(1)
    print "theapp: " + theapp

    xrePath = os.path.dirname(theapp)

    if options.valgrind:
        raise Exception("runbrowser isn't working with Valgrind at the moment.")
        #print "About to use valgrind"
        #debuggerInfoVG = automationutils.getDebuggerInfo(oldcwd, "valgrind", "", False)
        #debuggerInfoVG["args"] = options.vgargs.split(" ")
        #if automation.IS_MAC:
        #    debuggerInfoVG["args"].append("--dsymutil=yes")
        #slowness = 3.0
    else:
        debuggerInfoVG = None
        slowness = 1.0

    # browser environment
    browserEnv = automation.environment(xrePath=xrePath)
    gatherAssertionStacks = False  # windows output entangling (bug 573306); mac symbolizing slowness and output bloat
    if gatherAssertionStacks:
        browserEnv["XPCOM_DEBUG_BREAK"] = "stack"
    browserEnv["MOZ_GDB_SLEEP"] = "2"  # seconds
    if not options.valgrind and "-asan" not in theapp:
        browserEnv["MallocScribble"] = "1"
        browserEnv["MallocPreScribble"] = "1"
    if options.valgrind and automation.IS_LINUX:
        browserEnv["G_SLICE"] = "always-malloc"
    if automation.IS_DEBUG_BUILD and not options.valgrind and options.leakLogFile:
        browserEnv["XPCOM_MEM_LEAK_LOG"] = options.leakLogFile
    browserEnv["MOZ_DISABLE_SAFE_MODE_KEY"] = "1"

    # Defeat Lion's misguided attempt to stop Firefox from crashing repeatedly.
    # (I suspect "restorecount.txt" is the most important file to remove.)
    removeDirIfExists(os.path.expanduser("~/Library/Saved Application State/org.mozilla.nightly.savedState"))
    removeDirIfExists(os.path.expanduser("~/Library/Saved Application State/org.mozilla.nightlydebug.savedState"))

    cmdLineArgs = []
    if "#fuzz=" in url:
        cmdLineArgs.append("-fuzzinject")
    cmdLineArgs.append(url)

    print "RUNBROWSER INFO | runbrowser.py | runApp: start."
    print "RUNBROWSER INFO | runbrowser.py | " + url

    if options.background:
        automation.buildCommandLine = stripForegroundArg(automation.buildCommandLine)

    status = automation.runApp(None, browserEnv, theapp, profileDir, cmdLineArgs,
                               utilityPath=utilityDir,
                               xrePath=xrePath,
                               symbolsPath=options.symbolsDir,
                               debuggerInfo=debuggerInfoVG,
                               maxTime=400.0 * slowness,
                               timeout=200.0 * slowness)
    print "RUNBROWSER INFO | runbrowser.py | runApp: exited with status " + str(status)


def stripForegroundArg(buildCommandLine):
    def intercept(*args):
        cmd, args = buildCommandLine(*args)
        args = filter((lambda a: a != "-foreground"), args)
        return cmd, args
    return intercept


if __name__ == "__main__":
    runBrowser()

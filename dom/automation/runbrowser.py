#!/usr/bin/env python

import os
import sys
import shutil
import platform
from optparse import OptionParser

oldcwd = os.getcwd()
#os.chdir(SCRIPT_DIRECTORY)

def removeDirIfExists(d):
  if os.path.exists(d):
    shutil.rmtree(d, ignore_errors=True)

def runBrowser():
  parser = OptionParser()
  # we want to pass down everything from automation.__all__
  parser.add_option("--valgrind",
                    action = "store_true", dest = "valgrind",
                    default = False,
                    help = "use valgrind with the options given in --vgargs")
  parser.add_option("--vgargs",
                    action = "store", dest = "vgargs",
                    default = None,
                    help = "space-separated arguments to give to valgrind")
  parser.add_option("--symbols-dir",
                    action = "store", dest = "symbolsDir",
                    default = None)
  parser.add_option("--leak-log-file",
                    action = "store", dest = "leakLogFile",
                    default = None)
  options, args = parser.parse_args(sys.argv)

  reftestScriptDir = args[1]
  utilityDir = args[2]
  profileDir = args[3]
  url = args[4]

  sys.path.append(reftestScriptDir)
  from automation import Automation
  import automationutils

  automation = Automation()

  # also run automation.py's options parser, but don't give it any input
  aparser = OptionParser()
  automationutils.addCommonOptions(aparser, defaults=dict(zip(automation.__all__, [getattr(automation, x) for x in automation.__all__])))
  automation.addCommonOptions(aparser)
  aOptions = aparser.parse_args([])[0]

  theapp = os.path.join(reftestScriptDir, automation.DEFAULT_APP)
  if not os.path.exists(theapp):
    print "RUNBROWSER ERROR | runbrowser.py | Application %s doesn't exist." % theapp
    sys.exit(1)
  print "theapp: " + theapp

  if aOptions.xrePath is None:
    aOptions.xrePath = os.path.dirname(theapp)

  if options.valgrind:
    print "About to use valgrind"
    debuggerInfoVG = automationutils.getDebuggerInfo(oldcwd, "valgrind", "", False);
    debuggerInfoVG["args"] = options.vgargs.split(" ")
    if automation.IS_MAC:
      debuggerInfoVG["args"].append("--dsymutil=yes")
    slowness = 3.0
  else:
    debuggerInfoVG = None
    slowness = 1.0

  # browser environment
  browserEnv = automation.environment(xrePath = aOptions.xrePath)
  gatherAssertionStacks = not automation.IS_WIN32 # bug 573306
  browserEnv["XPCOM_DEBUG_BREAK"] = "stack" if gatherAssertionStacks else "warn"
  browserEnv["MOZ_GDB_SLEEP"] = "2" # seconds
  if not options.valgrind:
    browserEnv["MallocScribble"] = "1"
    browserEnv["MallocPreScribble"] = "1"
  if options.valgrind and automation.IS_LINUX:
    browserEnv["G_SLICE"] = "always-malloc"
  if automation.IS_DEBUG_BUILD and not options.valgrind and options.leakLogFile:
      browserEnv["XPCOM_MEM_LEAK_LOG"] = options.leakLogFile

  # Defeat Lion's misguided attempt to stop Firefox from crashing repeatedly. (I suspect "restorecount.txt" is the most important file to remove.)
  removeDirIfExists(os.path.expanduser("~/Library/Saved Application State/org.mozilla.nightly.savedState"))
  removeDirIfExists(os.path.expanduser("~/Library/Saved Application State/org.mozilla.nightlydebug.savedState"))

  print("RUNBROWSER INFO | runbrowser.py | runApp: start.")
  print("RUNBROWSER INFO | runbrowser.py | " + url)
  status = automation.runApp(None, browserEnv, theapp, profileDir,
                             [url],
                             utilityPath = utilityDir,
                             xrePath=aOptions.xrePath,
                             symbolsPath=options.symbolsDir,
                             debuggerInfo=debuggerInfoVG,
                             maxTime = 400.0 * slowness,
                             timeout = 200.0 * slowness
                             )
  print("RUNBROWSER INFO | runbrowser.py | runApp: exited with status " + str(status))

if __name__ == "__main__":
  runBrowser()


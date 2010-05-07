#!/usr/bin/env python

"""
Runs the DOM fuzzing harness.
Based on runreftest.py.  Uses automation.py.
"""


from __future__ import with_statement
import sys, shutil, os, signal, logging
from optparse import OptionParser
from tempfile import mkdtemp
import detect_assertions, detect_malloc_errors, detect_interesting_crashes, detect_leaks

# could also use sys._getframe().f_code.co_filename, but this seems cleaner
THIS_SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# Levels of unhappiness.
# These are in order from "most expected to least expected" rather than "most ok to worst".
# Fuzzing will note the level, and pass it to Lithium.
# Lithium is allowed to go to a higher level.
(DOM_FINE, DOM_TIMED_OUT_UNEXPECTEDLY, DOM_ABNORMAL_EXIT, DOM_FUZZER_COMPLAINED, DOM_VG_AMISS, DOM_NEW_LEAK, DOM_MALLOC_ERROR, DOM_NEW_ASSERT_OR_CRASH) = range(8)

oldcwd = os.getcwd()
#os.chdir(SCRIPT_DIRECTORY)

VALGRIND_ERROR_EXIT_CODE = 77

def getSignalName(num, default=None):
    for p in dir(signal):
        if p.startswith("SIG") and not p.startswith("SIG_"):
            if getattr(signal, p) == num:
                return p
    return default

def getFullPath(path):
  "Get an absolute path relative to oldcwd."
  return os.path.normpath(os.path.join(oldcwd, os.path.expanduser(path)))

def createDOMFuzzProfile(options, profileDir, valgrindMode):
  "Sets up a profile for domfuzz."

  # Set preferences.
  prefsFile = open(os.path.join(profileDir, "user.js"), "w")
  #prefsFile.write('user_pref("reftest.timeout", %d);\n' % (options.timeout * 1000)) # XXX an excellent idea
  prefsFile.write('user_pref("browser.dom.window.dump.enabled", true);\n')
  prefsFile.write('user_pref("ui.caretBlinkTime", -1);\n')

  for v in options.extraPrefs:
    thispref = v.split("=")
    if len(thispref) < 2:
      print "Error: syntax error in --setpref=" + v
      sys.exit(1)
    part = 'user_pref("%s", %s);\n' % (thispref[0], thispref[1])
    prefsFile.write(part)

  # no slow script dialogs
  prefsFile.write('user_pref("dom.max_script_run_time", 0);')
  prefsFile.write('user_pref("dom.max_chrome_script_run_time", 0);')

  # additional prefs for fuzzing
  prefsFile.write('user_pref("browser.sessionstore.resume_from_crash", false);\n')
  prefsFile.write('user_pref("layout.debug.enable_data_xbl", true);\n')
  prefsFile.write('user_pref("dom.disable_window_status_change", false);\n')
  prefsFile.write('user_pref("dom.disable_window_move_resize", true);\n')
  prefsFile.write('user_pref("browser.tabs.warnOnClose", false);\n')
  prefsFile.write('user_pref("browser.shell.checkDefaultBrowser", false);\n')
  prefsFile.write('user_pref("browser.EULA.override", true);\n')
  prefsFile.write('user_pref("security.warn_submit_insecure", false);\n')
  prefsFile.write('user_pref("security.warn_viewing_mixed", false);\n')

  # Turn off various things in firefox that try to update themselves,
  # to improve performance and sanity and reduce risk of hitting 479373.
  # http://support.mozilla.com/en-US/kb/Firefox+makes+unrequested+connections
  prefsFile.write('user_pref("browser.safebrowsing.enabled", false);\n')
  prefsFile.write('user_pref("browser.safebrowsing.malware.enabled", false);\n')
  prefsFile.write('user_pref("browser.search.update", false);\n')
  prefsFile.write('user_pref("app.update.enabled", false);\n')
  prefsFile.write('user_pref("extensions.update.enabled", false);\n')
  prefsFile.write('user_pref("extensions.blocklist.enabled", false);\n')
  prefsFile.write('user_pref("lightweightThemes.update.enabled", false);\n')
  prefsFile.write('user_pref("browser.microsummary.enabled", false);\n')
  
  # Extra prefs for Valgrind
  if valgrindMode:
    prefsFile.write('user_pref("javascript.options.jit.content", false);\n')
    prefsFile.write('user_pref("javascript.options.jit.chrome", false);\n')
    # XXX disable plugins

  prefsFile.close()

  # Install a domfuzz extension 'pointer file' into the profile.
  profileExtensionsPath = os.path.join(profileDir, "extensions")
  os.mkdir(profileExtensionsPath)
  domfuzzExtensionPath = os.path.join(THIS_SCRIPT_DIRECTORY, "..", "extension")
  extFile = open(os.path.join(profileExtensionsPath, "domfuzz@squarefree.com"), "w")
  extFile.write(domfuzzExtensionPath)
  extFile.close()
  
  # Give the profile an empty bookmarks file, so there are no live-bookmark requests
  shutil.copyfile(os.path.join(THIS_SCRIPT_DIRECTORY, "empty-bookmarks.html"), os.path.join(profileDir, "bookmarks.html"))

def getFirefoxBranch(appini):
  with file(appini) as f:
    for line in f:
      if line.startswith("SourceRepository="):
        line = line.rstrip()
        if line.endswith("/"):
          return line.split("/")[-2]
        else:
          return line.split("/")[-1]


class AmissLogHandler(logging.Handler):
  def __init__(self, knownPath):
    logging.Handler.__init__(self)
    self.newAssertionFailure = False
    self.mallocFailure = False
    self.knownPath = knownPath
    self.FRClines = []
    self.pid = None
    self.fullLogHead = []
    self.expectedToHang = True
    self.nsassertionCount = 0
    self.fuzzerComplained = False
  def emit(self, record):
    msg = record.msg
    msgLF = msg + "\n"
    if len(self.fullLogHead) < 100000:
      self.fullLogHead.append(msgLF)
    if self.pid == None and msg.startswith("INFO | automation.py | Application pid:"):
      self.pid = record.args[0]
      #print "Got the pid: " + repr(self.pid)
    if msg.find("FRC") != -1:
      self.FRClines.append(msgLF)
    if msg == "Not expected to hang":
      self.expectedToHang = False
    if msg.startswith("FAILURE:"):
      self.fuzzerComplained = True
      self.fullLogHead.append("@@@ " + msgLF)
    if msg.find("###!!! ASSERTION") != -1:
      self.nsassertionCount += 1
      if self.nsassertionCount == 100:
        print "rundomfuzz.py: not considering it a failure if browser hangs, because assertions are slow with stack-printing on. Please test in opt builds too, or fix the assertion bugs."
        self.expectedToHang = True
    if detect_assertions.scanLine(self.knownPath, msgLF):
      self.newAssertionFailure = True
      self.fullLogHead.append("@@@ New assertion: " + msgLF)
    if not self.mallocFailure and detect_malloc_errors.scanLine(msgLF):
      self.mallocFailure = True
      self.fullLogHead.append("@@@ Malloc is unhappy\n")

class FigureOutDirs:
  def __init__(self, browserDir):
    #self.appDir = None
    self.reftestFilesDir = None
    self.reftestScriptDir = None
    self.symbolsDir = None
    self.utilityDir = None

    if os.path.exists(os.path.join(browserDir, "dist")) and os.path.exists(os.path.join(browserDir, "tests")):
      # browserDir is a downloaded packaged build, perhaps downloaded with build_downloader.py.  Great!
      #self.appDir = os.path.join(browserDir, "dist")
      self.reftestFilesDir = os.path.join(browserDir, "tests", "reftest", "tests")
      self.reftestScriptDir = os.path.join(browserDir, "tests", "reftest")
      self.utilityDir = os.path.join(browserDir, "tests", "bin")
      self.symbolsDir = os.path.join(browserDir, "symbols")
    elif os.path.exists(os.path.join(browserDir, "..", "layout", "reftests")):
      # browserDir is an objdir whose parent is a srcdir.  That works too (more convenient for local builds)
      #self.appDir = browserDir
      self.reftestScriptDir = os.path.join(browserDir, "_tests", "reftest")
      self.reftestFilesDir = os.path.join(browserDir, "..")
      self.utilityDir = os.path.join(browserDir, "dist", "bin")  # on mac, looking inside the app would also work!
      self.symbolsDir = os.path.join(browserDir, "dist", "crashreporter-symbols")
    else:
      raise Exception("browserDir is not the kind of directory I expected")

    #if not os.path.exists(self.appDir):
    #  raise Exception("Oops! appDir does not exist!")
    if not os.path.exists(self.reftestScriptDir):
      raise Exception("Oops! reftestScriptDir does not exist!")
    if not os.path.exists(self.reftestFilesDir):
      raise Exception("Oops! reftestFilesDir does not exist!")
    if not os.path.exists(self.utilityDir):
      raise Exception("Oops! utilityDir does not exist!")

    if not os.path.exists(self.symbolsDir):
      self.symbolsDir = None
    if self.symbolsDir:
      self.symbolsDir = getFullPath(self.symbolsDir)

def rdfInit(browserDir, additionalArgs = []):
  """Fully prepare a Firefox profile, then return a function that will run Firefox with that profile."""
  
  dirs = FigureOutDirs(browserDir)

  # Fun issue: we don't know where automation.py is until we have our first argument,
  # but we can't parse our arguments until we have automation.py.  So the objdir
  # gets to be our first argument.
  print dirs.reftestScriptDir
  sys.path.append(dirs.reftestScriptDir)
  try:
    from automation import Automation
    import automationutils
  finally:
    sys.path.pop()

  automation = Automation()

  parser = OptionParser()

  # we want to pass down everything from automation.__all__
  automationutils.addCommonOptions(parser, defaults=dict(zip(automation.__all__, [getattr(automation, x) for x in automation.__all__])))
  automation.addCommonOptions(parser)
  parser.add_option("--valgrind",
                    action = "store_true", dest = "valgrind",
                    default = False,
                    help = "use valgrind with a reasonable set of options")
  parser.add_option("--appname",
                    action = "store", type = "string", dest = "app",
                    default = os.path.join(dirs.reftestScriptDir, automation.DEFAULT_APP),
                    help = "absolute path to application, overriding default")
  parser.add_option("--timeout",              
                    action = "store", dest = "timeout", type = "int", 
                    default = 1 * 60, # 1 minute
                    help = "Time out in specified number of seconds. [default %default s].")
  parser.add_option("--utility-path",
                    action = "store", type = "string", dest = "utilityPath",
                    default = dirs.utilityDir,
                    help = "absolute path to directory containing utility "
                           "programs (xpcshell, ssltunnel, certutil)")

  options, args = parser.parse_args(additionalArgs)

  options.app = getFullPath(options.app)
  print options.app
  if not os.path.exists(options.app):
    print "Error: Path %(app)s doesn't exist." % {"app": options.app}
    sys.exit(1)

  if options.xrePath is None:
    options.xrePath = os.path.dirname(options.app)
  else:
    # allow relative paths
    options.xrePath = getFullPath(options.xrePath)

  options.utilityPath = getFullPath(options.utilityPath)

  debuggerInfo = automationutils.getDebuggerInfo(oldcwd, options.debugger, options.debuggerArgs,
     options.debuggerInteractive);

  profileDir = None

  profileDir = mkdtemp()
  createDOMFuzzProfile(options, profileDir, options.valgrind)

  # browser environment
  browserEnv = automation.environment(xrePath = options.xrePath)
  browserEnv["XPCOM_DEBUG_BREAK"] = "warn"
  browserEnv["MOZ_GDB_SLEEP"] = "2" # seconds
  if not options.valgrind:
    browserEnv["MallocScribble"] = "1"
    browserEnv["MallocPreScribble"] = "1"

  automation.log.info("DOMFUZZ INFO | rundomfuzz.py | Getting Firefox version")
  firefoxBranch = getFirefoxBranch(os.path.normpath(os.path.join(options.app, "..", "application.ini")))
  automation.log.info("DOMFUZZ INFO | rundomfuzz.py | Firefox version: " + firefoxBranch)
  knownPath = os.path.join(THIS_SCRIPT_DIRECTORY, "..", "known", firefoxBranch)
  automation.log.info("DOMFUZZ INFO | rundomfuzz.py | Ignoring known bugs in: " + knownPath)

  # run once with -silent to let the extension manager do its thing
  # and then exit the app
  automation.log.info("DOMFUZZ INFO | rundomfuzz.py | Performing extension manager registration: start.\n")
  
  # Don't care about this |status|: |runApp()| reporting it should be enough.
  status = automation.runApp(None, browserEnv, options.app, profileDir,
                             ["-silent"],
                             utilityPath = options.utilityPath,
                             xrePath=options.xrePath,
                             symbolsPath=options.symbolsPath,
                             maxTime = options.timeout + 300.0,
                             timeout = options.timeout + 120.0
                             )
  # We don't care to call |automationutils.processLeakLog()| for this step.
  automation.log.info("\nDOMFUZZ INFO | rundomfuzz.py | Performing extension manager registration: end.")


  def levelAndLines(url, logPrefix=None):
    """Run Firefox using the profile created above, detecting bugs and stuff."""

    # This is a little sketchy, changing debugger and debuggerArgs after calling runApp once.
    # But it saves a lot of time, and by this point we know what knownPath and logPrefix are.
    if options.valgrind:
      print "About to use valgrind"
      assert not debuggerInfo
      debuggerInfo2 = automationutils.getDebuggerInfo(oldcwd, "valgrind", "", False);
      debuggerInfo2["args"] = [
        "--error-exitcode=" + str(VALGRIND_ERROR_EXIT_CODE),
        "--suppressions=" + os.path.join(knownPath, "valgrind.txt"),
        "--gen-suppressions=all"
      ]
      if automation.IS_MAC:
        debuggerInfo2["args"].append("--dsymutil=yes")
    else:
      debuggerInfo2 = debuggerInfo

    leakLogFile = None

    if automation.IS_DEBUG_BUILD and not options.valgrind:
        # This breaks if logPrefix is None. Not sure what to do. :(
        leakLogFile = logPrefix + "-leaks.txt"
        browserEnv["XPCOM_MEM_LEAK_LOG"] = leakLogFile

    automation.log.info("DOMFUZZ INFO | rundomfuzz.py | Running for fuzzage: start.\n")
    alh = AmissLogHandler(knownPath)
    automation.log.addHandler(alh)
    status = automation.runApp(None, browserEnv, options.app, profileDir,
                               [url],
                               utilityPath = options.utilityPath,
                               xrePath=options.xrePath,
                               debuggerInfo=debuggerInfo2,
                               symbolsPath=dirs.symbolsDir, # bypassing options, not sure this is a good idea
                               maxTime = options.timeout + 300.0,
                               timeout = options.timeout + 120.0
                               )
    automation.log.removeHandler(alh)
    automation.log.info("\nDOMFUZZ INFO | rundomfuzz.py | Running for fuzzage, status " + str(status))
    
    lev = DOM_FINE
  
    if alh.newAssertionFailure:
      lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)
    if alh.mallocFailure:
      lev = max(lev, DOM_MALLOC_ERROR)
    if alh.fuzzerComplained:
      lev = max(lev, DOM_FUZZER_COMPLAINED)

    if status < 0:
      # The program was terminated by a signal, which usually indicates a crash.
      # Mac/Linux only!
      signum = -status
      signame = getSignalName(signum, "unknown signal")
      automation.log.info("DOMFUZZ INFO | rundomfuzz.py | Terminated by signal " + str(signum) + " (" + signame + ")")
      if signum == signal.SIGKILL:
        if alh.expectedToHang or options.valgrind:
          print "Expected hang"
        else:
          print "Unexpected hang"
          lev = max(lev, DOM_TIMED_OUT_UNEXPECTEDLY)
      else:
        crashlog = None
        if signum != signal.SIGKILL and dirs.symbolsDir == None:
            crashlog = grabCrashLog(os.path.basename(options.app), alh.pid, None, signum)
        if crashlog:
          print open(crashlog).read()
          if detect_interesting_crashes.amiss(knownPath, crashlog, False, signame):
            automation.log.info("DOMFUZZ INFO | rundomfuzz.py | New crash")
            if logPrefix:
              shutil.copyfile(crashlog, logPrefix + "-crash.txt")
            lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)
          else:
            automation.log.info("DOMFUZZ INFO | rundomfuzz.py | Known crash")
    
    if options.valgrind and status == VALGRIND_ERROR_EXIT_CODE:
      lev = max(lev, DOM_VG_AMISS)
    elif status > 0:
      lev = max(lev, DOM_ABNORMAL_EXIT)

    if leakLogFile and status == 0 and detect_leaks.amiss(knownPath, leakLogFile, verbose=True):
      lev = max(lev, DOM_NEW_LEAK)
    elif leakLogFile:
      os.remove(leakLogFile)

    if (lev > DOM_FINE) and logPrefix:
      outlog = open(logPrefix + "-output.txt", "w")
      outlog.writelines(alh.fullLogHead)
      outlog.close()
  
    automation.log.info("DOMFUZZ INFO | rundomfuzz.py | Running for fuzzage, level " + str(lev) + ".")
  
    FRClines = alh.FRClines
    alh.close()
  
    return (lev, FRClines)
    
  return levelAndLines, options # return a closure along with the set of options


# XXX try to squeeze this into automation.py or automationutils.py
def grabCrashLog(progname, crashedPID, logPrefix, signum):
    import os, platform, time
    useLogFiles = isinstance(logPrefix, str)
    if useLogFiles:
        if os.path.exists(logPrefix + "-crash"):
            os.remove(logPrefix + "-crash")
        if os.path.exists(logPrefix + "-core"):
            os.remove(logPrefix + "-core")
    if platform.system() == "Darwin":
        macCrashLogFilename = None
        loops = 0
        while macCrashLogFilename == None:
            # Look for a core file, in case the user did "ulimit -c unlimited"
            coreFilename = "/cores/core." + str(crashedPID)
            if useLogFiles and os.path.exists(coreFilename):
                os.rename(coreFilename, logPrefix + "-core")
            # Find a crash log for the right process name and pid, preferring
            # newer crash logs (which sort last).
            crashLogDir = "~/Library/Logs/CrashReporter/" if platform.mac_ver()[0].startswith("10.5") else "~/Library/Logs/DiagnosticReports/"
            crashLogDir = os.path.expanduser(crashLogDir)
            try:
                crashLogs = os.listdir(crashLogDir)
            except (OSError, IOError), e:
                # Maybe this is the first crash ever on this computer, and the directory doesn't exist yet.
                crashLogs = []
            crashLogs = filter(lambda s: (s.startswith(progname + "_") or s.startswith(progname + "-bin_")), crashLogs)
            crashLogs.sort(reverse=True)
            for fn in crashLogs:
                fullfn = os.path.join(crashLogDir, fn)
                try:
                    c = file(fullfn)
                    firstLine = c.readline()
                    c.close()
                    if firstLine.rstrip().endswith("[" + str(crashedPID) + "]"):
                        macCrashLogFilename = fullfn
                        break

                except (OSError, IOError), e:
                    # Maybe the log was rotated out between when we got the list
                    # of files and when we tried to open this file.  If so, it's
                    # clearly not The One.
                    pass
            if macCrashLogFilename == None:
                # print "[grabCrashLog] Waiting for the crash log to appear..."
                time.sleep(0.100)
                loops += 1
                if loops > 2000:
                    # I suppose this might happen if the process corrupts itself so much that
                    # the crash reporter gets confused about the process name, for example.
                    print "grabCrashLog waited a long time, but a crash log for " + progname + " [" + str(crashedPID) + "] never appeared!"
                    break
        if macCrashLogFilename != None:
            if useLogFiles:
                os.rename(macCrashLogFilename, logPrefix + "-crash")
                return logPrefix + "-crash"
            else:
                return macCrashLogFilename
                #return open(macCrashLogFilename).read()
    return None



# For use by Lithium
def init(args):
  global levelAndLinesForLithium, minimumInterestingLevel, lithiumURL
  minimumInterestingLevel = int(args[0])
  browserDir = args[1]
  lithiumURL = args[2]
  levelAndLinesForLithium, options = rdfInit(browserDir, additionalArgs = args[3:])
def interesting(args, tempPrefix):
  actualLevel, lines = levelAndLinesForLithium(lithiumURL, logPrefix = tempPrefix)
  return actualLevel >= minimumInterestingLevel
# no appropriate callback from lithium for deleteProfile -- especially since we don't get to try..finally for Ctrl+C
# could this be fixed by using a generator with yield??

if __name__ == "__main__":
  import tempfile
  logPrefix = tempfile.mkdtemp() + "t"
  print logPrefix
  browserDir = sys.argv[1]
  url = sys.argv[2]
  level, lines = rdfInit(browserDir, additionalArgs = sys.argv[3:])[0](url, logPrefix)
  print level
  #deleteProfile()

#def deleteProfile():
#  if profileDir:
#    shutil.rmtree(profileDir)

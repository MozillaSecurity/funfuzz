#!/usr/bin/env python

"""

Runs Firefox with DOM fuzzing.  Identifies output that indicates that a bug has been found.

We run runbrowser.py through a (s)ubprocess.  runbrowser.py (i)mports automation.py.  This setup allows us to postprocess all automation.py output, including crash logs.

        i                  i                 s*                i                 s
bot.py --> loopdomfuzz.py --> rundomfuzz.py --> runbrowser.py --> automation.py+ --> firefox-bin
                                   ^
                                   |
                                   |
                              you are here

"""


from __future__ import with_statement
import sys
import shutil
import os
import platform
import signal
import glob
from optparse import OptionParser
from tempfile import mkdtemp
import subprocess

import runbrowser

import detect_assertions
import detect_malloc_errors
import detect_interesting_crashes
import detect_leaks

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

def createDOMFuzzProfile(profileDir, valgrindMode):
  "Sets up a profile for domfuzz."

  # Set preferences.
  
  prefsText = """
// Disable slow script dialogs.
user_pref("dom.max_script_run_time", 0);
user_pref("dom.max_chrome_script_run_time", 0);

// Set additional prefs for fuzzing.
user_pref("browser.dom.window.dump.enabled", true);
user_pref("ui.caretBlinkTime", -1);
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("layout.debug.enable_data_xbl", true);
user_pref("dom.disable_window_status_change", false);
user_pref("dom.disable_window_move_resize", true);
user_pref("dom.disable_open_during_load", false);
user_pref("extensions.enabledScopes", 3);

// Disable first-run annoyances.
user_pref("browser.tabs.warnOnClose", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.EULA.override", true);
user_pref("security.warn_submit_insecure", false);
user_pref("security.warn_viewing_mixed", false);

// Turn off various things in firefox that try to update themselves,
// to improve performance and sanity.
// http://support.mozilla.com/en-US/kb/Firefox+makes+unrequested+connections
user_pref("browser.safebrowsing.enabled", false);
user_pref("browser.safebrowsing.malware.enabled", false);
user_pref("browser.search.update", false);
user_pref("app.update.enabled", false);
user_pref("extensions.update.enabled", false);
user_pref("extensions.getAddons.cache.enabled", false);
user_pref("extensions.blocklist.enabled", false);
user_pref("extensions.showMismatchUI", false);
user_pref("extensions.testpilot.runStudies", false);
user_pref("lightweightThemes.update.enabled", false);
user_pref("browser.microsummary.enabled", false);
"""

  if valgrindMode:
    prefsText = prefsText + """
user_pref("javascript.options.jit.content", false);
user_pref("javascript.options.jit.chrome", false);
"""
  
  prefsFile = open(os.path.join(profileDir, "user.js"), "w")
  prefsFile.write(prefsText)
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

def getFirefoxBranch(app):
  appini = os.path.normpath(os.path.join(app, "..", "application.ini"))
  with file(appini) as f:
    for line in f:
      if line.startswith("SourceRepository="):
        line = line.rstrip()
        if line.endswith("/"):
          return line.split("/")[-2]
        else:
          return line.split("/")[-1]

def getKnownPath(app):
  firefoxBranch = getFirefoxBranch(app)
  knownPath = os.path.join(THIS_SCRIPT_DIRECTORY, "..", "known", firefoxBranch)
  if not os.path.exists(knownPath):
    print "Missing knownPath: " + knownPath
    sys.exit(1)
  return knownPath

class AmissLogHandler:
  def __init__(self, knownPath):
    self.newAssertionFailure = False
    self.mallocFailure = False
    self.knownPath = knownPath
    self.FRClines = []
    self.pid = None
    self.fullLogHead = []
    self.summaryLog = []
    self.expectedToHang = True
    self.nsassertionCount = 0
    self.fuzzerComplained = False
    self.sawProcessedCrash = False
    self.crashIsKnown = False
    self.timedOut = False
  def processLine(self, msgLF):
    msgLF = stripBeeps(msgLF)
    msg = msgLF.rstrip("\n")
    if len(self.fullLogHead) < 100000:
      self.fullLogHead.append(msgLF)
    pidprefix = "INFO | automation.py | Application pid:"
    if self.pid == None and msg.startswith(pidprefix):
      self.pid = int(msg[len(pidprefix):])
      print "Firefox pid: " + str(self.pid)
    if msg.find("FRC") != -1:
      self.FRClines.append(msgLF)
    if msg == "Not expected to hang":
      self.expectedToHang = False
    if msg.startswith("FAILURE:"):
      self.fuzzerComplained = True
      self.printAndLog("@@@ " + msg)
    if msg.find("###!!! ASSERTION") != -1:
      self.nsassertionCount += 1
      if self.nsassertionCount == 100:
        print "rundomfuzz.py: not considering it a failure if browser hangs, because assertions are slow with stack-printing on. Please test in opt builds too, or fix the assertion bugs."
        self.expectedToHang = True
    if detect_assertions.scanLine(self.knownPath, msgLF):
      self.newAssertionFailure = True
      self.printAndLog("@@@ " + msg)
    if not self.mallocFailure and detect_malloc_errors.scanLine(msgLF) and "Bug 592118" == "UNFIXED":
      self.mallocFailure = True
      self.printAndLog("@@@ Malloc is unhappy")
    if (msg.startswith("TEST-UNEXPECTED-FAIL | automation.py | application timed out") or
       msg.startswith("TEST-UNEXPECTED-FAIL | automation.py | application ran for longer")):
      self.timedOut = True
      self.crashIsKnown = True
    if msg == "PROCESS-CRASH | automation.py | application crashed (minidump found)":
      print "We have a crash on our hands!"
      self.sawProcessedCrash = True
    if self.sawProcessedCrash and detect_interesting_crashes.isKnownCrashSignature(msg):
      print "Known crash signature: " + msg
      self.crashIsKnown = True
    if msg == "** Unknown exception behavior":
      # Bug 550306 is a xul crash that causes a stack overflow.
      # Bug 507876 is a breakpad issue that means stack overflows don't give me stack traces on Mac.
      # The combination means we lose.
      print "%%% This is probably a too-much-recursion crash. It will be treated as a known crash."
      self.crashIsKnown = True
  def printAndLog(self, msg):
    print "$ " + msg
    self.fullLogHead.append(msg + "\n")
    self.summaryLog.append(msg + "\n")

def stripBeeps(s):
  """Strip BEL characters, in order to make copy-paste happier and avoid triggering text/plain binary-sniffing in web browsers."""
  return s.replace("\x07", "")

class FigureOutDirs:
  def __init__(self, browserDir):
    #self.appDir = None
    self.reftestFilesDir = None
    self.reftestScriptDir = None
    self.symbolsDir = None
    self.utilityDir = None
    self.stackwalk = None
    if not os.path.exists(browserDir):
      raise Exception("browserDir (%s) does not exist" % browserDir)

    if os.path.exists(os.path.join(browserDir, "dist")) and os.path.exists(os.path.join(browserDir, "tests")):
      # browserDir is a downloaded packaged build, perhaps downloaded with build_downloader.py.  Great!
      #self.appDir = os.path.join(browserDir, "dist")
      self.reftestFilesDir = os.path.join(browserDir, "tests", "reftest", "tests")
      self.reftestScriptDir = os.path.join(browserDir, "tests", "reftest")
      self.utilityDir = os.path.join(browserDir, "tests", "bin")
      self.symbolsDir = os.path.join(browserDir, "symbols")
      possible_stackwalk_fn = "minidump_stackwalk.exe" if (platform.system() in ("Microsoft", "Windows")) else "minidump_stackwalk"
      possible_stackwalk = os.path.join(browserDir, possible_stackwalk_fn)
      if (not os.environ.get('MINIDUMP_STACKWALK', None) and
          not os.environ.get('MINIDUMP_STACKWALK_CGI', None) and
          os.path.exists(possible_stackwalk)):
        self.stackwalk = possible_stackwalk
    elif os.path.exists(os.path.join(browserDir, "..", "layout", "reftests")):
      # browserDir is an objdir whose parent is a srcdir.  That works too (more convenient for local builds)
      #self.appDir = browserDir
      self.reftestScriptDir = os.path.join(browserDir, "_tests", "reftest")
      self.reftestFilesDir = os.path.join(browserDir, "..")
      self.utilityDir = os.path.join(browserDir, "dist", "bin")  # on mac, looking inside the app would also work!
      self.symbolsDir = os.path.join(browserDir, "dist", "crashreporter-symbols")
    else:
      raise Exception("browserDir should be an objdir-in-srcdir or a Tinderbox build downloaded with build_downloader.py")

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

def rdfInit(args):
  """Fully prepare a Firefox profile, then return a function that will run Firefox with that profile."""
  
  parser = OptionParser()
  parser.add_option("--valgrind",
                    action = "store_true", dest = "valgrind",
                    default = False,
                    help = "use valgrind with a reasonable set of options")
  parser.add_option("-m", "--minlevel",
                    type = "int", dest = "minimumInterestingLevel",
                    default = DOM_FINE + 1,
                    help = "minimum domfuzz level for lithium to consider the testcase interesting")
  options, args = parser.parse_args(args)

  browserDir = args[0]
  dirs = FigureOutDirs(getFullPath(browserDir))

  options.argURL = args[1] if len(args) > 1 else "" # used by standalone (optional) and lithium but not loopdomfuzz
  options.browserDir = browserDir # used by loopdomfuzz

  profileDir = mkdtemp(prefix="domfuzz-rdf-profile")
  createDOMFuzzProfile(profileDir, options.valgrind)

  runBrowserOptions = []
  if dirs.symbolsDir:
    runBrowserOptions.append("--symbols-dir=" + dirs.symbolsDir)

  env = os.environ
  if dirs.stackwalk:
    env['MINIDUMP_STACKWALK'] = dirs.stackwalk
  runBrowserArgs = [dirs.reftestScriptDir, dirs.utilityDir, profileDir]
  runbrowserpy = ["python", "-u", os.path.join(THIS_SCRIPT_DIRECTORY, "runbrowser.py")]

  close_fds = sys.platform != 'win32'
  # run once with -silent to let the extension manager do its thing, and to get knownPath
  runbrowser = subprocess.Popen(
                   runbrowserpy + runBrowserOptions + runBrowserArgs + ["silent"],
                   stdin = None,
                   stdout = subprocess.PIPE,
                   stderr = subprocess.STDOUT,
                   env = env,
                   close_fds = close_fds)

  knownPath = None

  while True:
    line = runbrowser.stdout.readline()
    if line != '':
      #print ">> " + line.rstrip("\n")
      if line.startswith("theapp: "):
        knownPath = getKnownPath(line[8:].rstrip())
    else:
      break

  if not knownPath:
    raise Exception("Didn't get a knownPath")
    
  detect_interesting_crashes.readIgnoreList(knownPath)

  if options.valgrind:
    runBrowserOptions.append("--valgrind")
    runBrowserOptions.append("--vgargs="
      "--error-exitcode=" + str(VALGRIND_ERROR_EXIT_CODE) + " " +
      "--suppressions=" + os.path.join(knownPath, "valgrind.txt") + " " +  # don't have a knownPath yet :(
      "--gen-suppressions=all"
    )
  
  def deleteProfile():
    if profileDir:
      print "Deleting Firefox profile in " + profileDir
      shutil.rmtree(profileDir)

  def levelAndLines(url, logPrefix=None):
    """Run Firefox using the profile created above, detecting bugs and stuff."""
    
    leakLogFile = logPrefix + "-leaks.txt"

    runbrowser = subprocess.Popen(
                     runbrowserpy + ["--leak-log-file=" + leakLogFile] + runBrowserOptions + runBrowserArgs + [url],
                     stdin = None,
                     stdout = subprocess.PIPE,
                     stderr = subprocess.STDOUT,
                     env = env,
                     close_fds = close_fds)
  
    alh = AmissLogHandler(knownPath)
  
    statusLinePrefix = "RUNBROWSER INFO | runbrowser.py | runApp: exited with status "
    status = -9000

    # NB: not using 'for line in runbrowser.stdout' because that uses a hidden buffer
    # see http://docs.python.org/library/stdtypes.html#file.next
    while True:
      line = runbrowser.stdout.readline()
      if line != '':
        print line.rstrip("\n")
        alh.processLine(line)
        if line.startswith(statusLinePrefix):
          status = int(line[len(statusLinePrefix):])
      else:
        break
    
    lev = DOM_FINE

    if alh.newAssertionFailure:
      lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)
    if alh.mallocFailure:
      lev = max(lev, DOM_MALLOC_ERROR)
    if alh.fuzzerComplained:
      lev = max(lev, DOM_FUZZER_COMPLAINED)

    if alh.timedOut:
      if alh.expectedToHang or options.valgrind:
        alh.printAndLog("%%% An expected hang")
      else:
        alh.printAndLog("@@@ Unexpected hang")
        lev = max(lev, DOM_TIMED_OUT_UNEXPECTEDLY)
    elif alh.sawProcessedCrash:
      if alh.crashIsKnown:
        alh.printAndLog("%%% Known crash (from minidump_stackwalk)")
      else:
        alh.printAndLog("@@@ New crash (from minidump_stackwalk)")
        lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)
    elif options.valgrind and status == VALGRIND_ERROR_EXIT_CODE:
      alh.printAndLog("@@@ Valgrind complained")
      lev = max(lev, DOM_VG_AMISS)
    elif status > 0:
      alh.printAndLog("@@@ Abnormal exit (status %d)" % status)
      lev = max(lev, DOM_ABNORMAL_EXIT)
    elif status < 0:
      # The program was terminated by a signal, which usually indicates a crash.
      # Mac/Linux only!  And maybe Mac only!
      signum = -status
      signame = getSignalName(signum, "unknown signal")
      print("DOMFUZZ INFO | rundomfuzz.py | Terminated by signal " + str(signum) + " (" + signame + ")")
      if platform.system() == "Darwin" and signum != signal.SIGKILL and signum != signal.SIGTERM and not alh.sawProcessedCrash:
        # well, maybe the OS crash reporter picked it up.
        appName = "firefox-bin" # should be 'os.path.basename(theapp)' but whatever
        crashlog = grabCrashLog(appName, alh.pid, None, signum)
        if crashlog:
          print open(crashlog).read()
          if detect_interesting_crashes.amiss(knownPath, crashlog, False, signame):
            alh.printAndLog("@@@ New crash (from mac crash reporter)")
            if logPrefix:
              shutil.copyfile(crashlog, logPrefix + "-crash.txt")
            lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)
          else:
            alh.printAndLog("%%% Known crash (from mac crash reporter)")

    if os.path.exists(leakLogFile) and status == 0 and detect_leaks.amiss(knownPath, leakLogFile, verbose=True):
      alh.printAndLog("@@@ Unexpected leak or leak pattern in " + os.path.basename(leakLogFile))
      lev = max(lev, DOM_NEW_LEAK)
    elif leakLogFile:
      # Remove the main leak log file, plus any plugin-process leak log files
      for f in glob.glob(leakLogFile + "*"):
        os.remove(f)

    if (lev > DOM_FINE) and logPrefix:
      outlog = open(logPrefix + "-output.txt", "w")
      outlog.writelines(alh.fullLogHead)
      outlog.close()
      subprocess.call(["gzip", logPrefix + "-output.txt"])
      summaryLogFile = open(logPrefix + "-summary.txt", "w")
      summaryLogFile.writelines(alh.summaryLog)
      summaryLogFile.close()
  
    print("DOMFUZZ INFO | rundomfuzz.py | Running for fuzzage, level " + str(lev) + ".")
  
    FRClines = alh.FRClines
  
    return (lev, FRClines)
    
  return levelAndLines, deleteProfile, options # return a closure along with the set of options


# should eventually try to squeeze this into automation.py or automationutils.py
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
  global levelAndLinesForLithium, deleteProfileForLithium, minimumInterestingLevel, lithiumURL
  levelAndLinesForLithium, deleteProfileForLithium, options = rdfInit(args)
  minimumInterestingLevel = options.minimumInterestingLevel
  lithiumURL = options.argURL
def interesting(args, tempPrefix):
  actualLevel, lines = levelAndLinesForLithium(lithiumURL, logPrefix = tempPrefix)
  return actualLevel >= minimumInterestingLevel
def cleanup(args):
  # we don't get to try..finally for Ctrl+C.
  # could this be fixed by using a generator with yield?
  deleteProfileForLithium()


if __name__ == "__main__":
  logPrefix = os.path.join(mkdtemp(prefix="domfuzz-rdf-main"), "t")
  print logPrefix
  levelAndLines, deleteProfileForMain, options = rdfInit(sys.argv[1:])
  level, lines = levelAndLines(options.argURL or "http://www.google.com/", logPrefix)
  print level
  #deleteProfileForMain()

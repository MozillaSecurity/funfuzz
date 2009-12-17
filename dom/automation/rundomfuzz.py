#!/usr/bin/env python

"""
Runs the DOM fuzzing harness.
Based on runreftest.py.  Uses automation.py.
"""


from __future__ import with_statement
import sys, shutil, os, signal, logging
from optparse import OptionParser
from tempfile import mkdtemp
import detect_assertions, detect_malloc_errors, detect_interesting_crashes

# could also use sys._getframe().f_code.co_filename, but this seems cleaner
THIS_SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# Levels of unhappiness.
# These are in order from "most expected to least expected" rather than "most ok to worst".
# Fuzzing will note the level, and pass it to Lithium.
# Lithium is allowed to go to a higher level.
(DOM_FINE, DOM_TIMED_OUT, DOM_ABNORMAL_EXIT, DOM_VG_AMISS, DOM_NEW_LEAK, DOM_MALLOC_ERROR, DOM_NEW_ASSERT_OR_CRASH) = range(7)

oldcwd = os.getcwd()
#os.chdir(SCRIPT_DIRECTORY)

def getSignalName(num, default=None):
    for p in dir(signal):
        if p.startswith("SIG") and not p.startswith("SIG_"):
            if getattr(signal, p) == num:
                return p
    return default

def getFullPath(path):
  "Get an absolute path relative to oldcwd."
  return os.path.normpath(os.path.join(oldcwd, os.path.expanduser(path)))

def createDOMFuzzProfile(options, profileDir):
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
        return line.split("/")[-2]


class AmissLogHandler(logging.Handler):
  def __init__(self, knownPath):
    logging.Handler.__init__(self)
    self.newAssertionFailure = False
    self.mallocFailure = False
    self.knownPath = knownPath
    self.FRClines = []
    self.pid = None
    self.fullLogHead = []
  def emit(self, record):
    msg = record.msg
    msgLF = msg + "\n"
    if len(self.fullLogHead) < 100000:
      self.fullLogHead.append(msgLF)
    if self.pid == None and msg.startswith("INFO | automation.py | Application pid:"):
      self.pid = record.args[0]
      print "Got the pid!" + repr(self.pid)
    if msg.find("FRC") != -1:
      self.FRClines.append(msgLF)
    if detect_assertions.scanLine(self.knownPath, msgLF):
      self.newAssertionFailure = True
      self.fullLogHead.append("@@@ New assertion: " + msgLF)
    if not self.mallocFailure and detect_malloc_errors.scanLine(msgLF):
      self.mallocFailure = True
      self.fullLogHead.append("@@@ Malloc is unhappy\n")

def levelAndLines(browserObjDir, url, additionalArgs = [], logPrefix = None):

  # Relying on reftest, which should exist in any --enable-tests build!
  # This directory contains a compiled automation.py and stuff.
  # Fun issue: we don't know where automation.py is until we have our first argument,
  # but we can't parse our arguments until we have automation.py.  So the objdir
  # gets to be our first argument.
  try:
    REFTEST_SCRIPT_DIRECTORY = os.path.join(browserObjDir, "_tests", "reftest")
    sys.path.append(REFTEST_SCRIPT_DIRECTORY)
    import automation
    import automationutils
  except (ImportError, IndexError):
    print "First argument to rundomfuzz.py must be a Firefox objdir built with --enable-tests."
    sys.exit(2)

  parser = OptionParser()

  # we want to pass down everything from automation.__all__
  automationutils.addCommonOptions(parser, defaults=dict(zip(automation.__all__, [getattr(automation, x) for x in automation.__all__])))
  automation.addExtraCommonOptions(parser)
  parser.add_option("--appname",
                    action = "store", type = "string", dest = "app",
                    default = os.path.join(REFTEST_SCRIPT_DIRECTORY, automation.DEFAULT_APP),
                    help = "absolute path to application, overriding default")
  parser.add_option("--timeout",              
                    action = "store", dest = "timeout", type = "int", 
                    default = 1 * 60, # 1 minute
                    help = "Time out in specified number of seconds. [default %default s].")
  parser.add_option("--utility-path",
                    action = "store", type = "string", dest = "utilityPath",
                    default = automation.DIST_BIN,
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

  if options.symbolsPath:
    options.symbolsPath = getFullPath(options.symbolsPath)
  options.utilityPath = getFullPath(options.utilityPath)

  debuggerInfo = automationutils.getDebuggerInfo(oldcwd, options.debugger, options.debuggerArgs,
     options.debuggerInteractive);

  profileDir = None
  try:
    profileDir = mkdtemp()
    createDOMFuzzProfile(options, profileDir)

    # browser environment
    browserEnv = automation.environment(xrePath = options.xrePath)
    browserEnv["XPCOM_DEBUG_BREAK"] = "stack"
    browserEnv["MOZ_GDB_SLEEP"] = "2" # seconds
    browserEnv["MallocScribble"] = "1"
    browserEnv["MallocPreScribble"] = "1"

    # Enable leaks detection to its own log file.
    #leakLogFile = os.path.join(profileDir, "runreftest_leaks.log")
    #browserEnv["XPCOM_MEM_BLOAT_LOG"] = leakLogFile
    # not XPCOM_MEM_LEAK_LOG??? see automationutils.py comments about these two env vars.

    automation.log.info("DOMFUZZ INFO | rundomfuzz.py | Getting Firefox version")
    firefoxBranch = getFirefoxBranch(os.path.join(automation.DIST_BIN, "application.ini"))
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
                               symbolsPath=options.symbolsPath)
    # We don't care to call |automationutils.processLeakLog()| for this step.
    automation.log.info("\nDOMFUZZ INFO | rundomfuzz.py | Performing extension manager registration: end.")

    # Remove the leak detection file so it can't "leak" to the tests run.
    # The file is not there if leak logging was not enabled in the application build.
    #if os.path.exists(leakLogFile):
    #  os.remove(leakLogFile)

    # then again to actually run domfuzz
    automation.log.info("DOMFUZZ INFO | rundomfuzz.py | Running for fuzzage: start.\n")
    alh = AmissLogHandler(knownPath)
    automation.log.addHandler(alh)
    status = automation.runApp(None, browserEnv, options.app, profileDir,
                               [url],
                               utilityPath = options.utilityPath,
                               xrePath=options.xrePath,
                               debuggerInfo=debuggerInfo,
                               symbolsPath=options.symbolsPath,
                               timeout = options.timeout + 120.0,
                               maxTime = options.timeout + 300.0)
    automation.log.removeHandler(alh)
    automation.log.info("\nDOMFUZZ INFO | rundomfuzz.py | Running for fuzzage, status " + str(status))
    
    lev = DOM_FINE

    if alh.newAssertionFailure:
      lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)
    #if runthis[0] != "valgrind" and status == 0 and detect_leaks.amiss(logPrefix):
    #  lev = max(lev, DOM_NEW_LEAK)
    if alh.mallocFailure:
      lev = max(lev, DOM_MALLOC_ERROR)

    if status < 0:
      # The program was terminated by a signal, which usually indicates a crash.
      # Mac/Linux only!
      signum = -status
      signame = getSignalName(signum, "unknown signal")
      automation.log.info("DOMFUZZ INFO | rundomfuzz.py | Terminated by signal " + str(signum) + " (" + signame + ")")
      if signum == signal.SIGKILL:
        lev = max(lev, DOM_TIMED_OUT)
      else:
        crashlog = None
        if signum != signal.SIGKILL:
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
    
    if status > 0:
      lev = max(lev, DOM_ABNORMAL_EXIT)

    if (lev > DOM_TIMED_OUT) and logPrefix:
      outlog = open(logPrefix + "-output.txt", "w")
      outlog.writelines(alh.fullLogHead)
      outlog.close()

    #if sta == ntr.TIMED_OUT:
    #  lev = max(lev, DOM_TIMED_OUT)
    #if runthis[0] == "valgrind" and detect_valgrind_errors.amiss(logPrefix + "-vg.xml", True):
    #  lev = max(lev, DOM_VG_AMISS)

    automation.log.info("DOMFUZZ INFO | rundomfuzz.py | Running for fuzzage, level " + str(lev) + ".")
  finally:
    if profileDir:
      shutil.rmtree(profileDir)

  FRClines = alh.FRClines
  alh.close()

  return (lev, FRClines)


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
            if platform.mac_ver()[0].startswith("10.4"):
                # Tiger doesn't create crash logs for aborts.
                if signum == signal.SIGABRT:
                    #print "[grabCrashLog] No crash logs for aborts on Tiger."
                    break
                # On Tiger, the crash log file just grows and grows, and it's hard to tell
                # if the right crash is in there.  So sleep even if the file already exists.
                time.sleep(2)
                tigerCrashLogName = os.path.expanduser("~/Library/Logs/CrashReporter/" + progname + ".crash.log")
                if os.path.exists(tigerCrashLogName):
                    macCrashLogFilename = tigerCrashLogName
                    break
                tigerCrashLogName = os.path.expanduser("~/Library/Logs/CrashReporter/" + progname + "-bin.crash.log")
                if os.path.exists(tigerCrashLogName):
                    macCrashLogFilename = tigerCrashLogName
                    break
            elif platform.mac_ver()[0].startswith("10.5") or platform.mac_ver()[0].startswith("10.6"):
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
def interesting(args, tempPrefix):
    minimumInterestingLevel = int(args[0])
    browserObjDir = args[1]
    url = args[2]
    actualLevel, lines = levelAndLines(browserObjDir, url, args[3:])
    return actualLevel >= minimumInterestingLevel

if __name__ == "__main__":
  level, lines = levelAndLines(sys.argv[1], sys.argv[2], sys.argv[3:])
  print level

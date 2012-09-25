#!/usr/bin/env python

"""

Runs Firefox with DOM fuzzing.  Identifies output that indicates that a bug has been found.

We run runbrowser.py through a (s)ubprocess.  runbrowser.py (i)mports automation.py.  This setup allows us to postprocess all automation.py output, including crash logs.

        i                  i                     s*                i                  s
bot.py --> loopdomfuzz.py --> domInteresting.py --> runbrowser.py --> automation.py+ --> firefox-bin
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
import re
from optparse import OptionParser
from tempfile import mkdtemp
import subprocess

# could also use sys._getframe().f_code.co_filename, but this seems cleaner
THIS_SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

p1 = os.path.abspath(os.path.join(THIS_SCRIPT_DIRECTORY, os.pardir, os.pardir, 'detect'))
sys.path.insert(0, p1)
import detect_assertions
import detect_malloc_errors
import detect_interesting_crashes
import detect_leaks

path2 = os.path.abspath(os.path.join(THIS_SCRIPT_DIRECTORY, os.pardir, os.pardir, 'util'))
sys.path.append(path2)
from subprocesses import grabCrashLog, isMac, isWin
import asanSymbolize

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

def writePrefs(profileDir, extraPrefs):
    prefsText = """
  // Disable slow script dialogs.
  user_pref("dom.max_script_run_time", 0);
  user_pref("dom.max_chrome_script_run_time", 0);

  // Set additional prefs for fuzzing.
  user_pref("browser.dom.window.dump.enabled", true);
  user_pref("browser.sessionstore.resume_from_crash", false);
  user_pref("layout.debug.enable_data_xbl", true);
  user_pref("dom.disable_window_status_change", false);
  user_pref("dom.disable_window_move_resize", false);
  user_pref("dom.disable_open_during_load", false);
  user_pref("dom.disable_window_flip", false);
  user_pref("extensions.enabledScopes", 3);
  user_pref("extensions.autoDisableScopes", 10);
  user_pref("extensions.update.notifyUser", false);
  user_pref("nglayout.debug.disable_xul_cache", true);
  user_pref("security.fileuri.strict_origin_policy", false);
  user_pref("dom.min_background_timeout_value", 4);

  // Disable a timer-based drawWindow call in favor of fuzzPriv.callDrawWindow.
  user_pref("browser.pageThumbs.enabled", false);

  // Reset things (on each startup) that might be set by fuzzing
  user_pref("javascript.options.gczeal", 0);

  // Disable first-run annoyances.
  user_pref("browser.tabs.warnOnClose", false);
  user_pref("browser.shell.checkDefaultBrowser", false);
  user_pref("browser.EULA.override", true);
  user_pref("security.warn_submit_insecure", false);
  user_pref("security.warn_viewing_mixed", false);
  user_pref("toolkit.telemetry.prompted", 2);
  user_pref("browser.rights.3.shown", true);
  user_pref("browser.firstrun.show.localepicker", false);
  user_pref("browser.firstrun.show.uidiscovery", false);
  user_pref("browser.startup.page", 0); // use about:blank, not browser.startup.homepage

  // Suppress automatic safe mode after crashes.
  user_pref("toolkit.startup.max_resumed_crashes", -1);

  // Turn off various things in firefox that try to contact servers,
  // to improve performance and sanity.
  // http://support.mozilla.com/en-US/kb/Firefox+makes+unrequested+connections
  user_pref("browser.safebrowsing.enabled", false);
  user_pref("browser.safebrowsing.malware.enabled", false);
  user_pref("browser.search.update", false);
  user_pref("app.update.enabled", false);
  user_pref("app.update.stage.enabled", false);
  user_pref("app.update.staging.enabled", false);
  user_pref("extensions.update.enabled", false);
  user_pref("extensions.getAddons.cache.enabled", false);
  user_pref("extensions.blocklist.enabled", false);
  user_pref("extensions.showMismatchUI", false);
  user_pref("extensions.testpilot.runStudies", false);
  user_pref("lightweightThemes.update.enabled", false);
  user_pref("browser.microsummary.enabled", false);
  user_pref("toolkit.telemetry.server", "");
  """

    prefsText += extraPrefs

    with open(os.path.join(profileDir, "prefs.js"), "w") as prefsFile:
        prefsFile.write(prefsText)


def createDOMFuzzProfile(profileDir):
    "Sets up a profile for domfuzz."

    # Install a domfuzz extension 'pointer file' into the profile.
    profileExtensionsPath = os.path.join(profileDir, "extensions")
    os.mkdir(profileExtensionsPath)
    domfuzzExtensionPath = os.path.join(THIS_SCRIPT_DIRECTORY, os.pardir, "extension")
    with open(os.path.join(profileExtensionsPath, "domfuzz@squarefree.com"), "w") as extFile:
        extFile.write(domfuzzExtensionPath)

valgrindComplaintRegexp = re.compile("^==\d+== ")

class AmissLogHandler:
    def __init__(self, knownPath):
        self.newAssertionFailure = False
        self.mallocFailure = False
        self.knownPath = knownPath
        self.FRClines = []
        self.theapp = None
        self.pid = None
        self.fullLogHead = []
        self.summaryLog = []
        self.expectedToHang = True
        self.expectedToLeak = True
        self.expectedToRenderInconsistently = False
        self.sawOMGLEAK = False
        self.nsassertionCount = 0
        self.sawFatalAssertion = False
        self.fuzzerComplained = False
        self.crashProcessor = None
        self.crashBoringBits = False
        self.crashMightBeTooMuchRecursion = False
        self.crashIsKnown = False
        self.timedOut = False
        self.sawValgrindComplaint = False
        self.expectChromeFailure = False
        self.sawChromeFailure = False
        detect_interesting_crashes.resetCounts()
    def processLine(self, msgLF):
        msgLF = stripBeeps(msgLF)
        if self.crashProcessor == "asan":
            msgLF = asanSymbolize.symbolize(msgLF)
        msg = msgLF.rstrip("\n")
        if len(self.fullLogHead) < 100000:
            self.fullLogHead.append(msgLF)
        pidprefix = "INFO | automation.py | Application pid:"
        if self.pid == None and msg.startswith(pidprefix):
            self.pid = int(msg[len(pidprefix):])
            #print "Firefox pid: " + str(self.pid)
        theappPrefix = "theapp: "
        if self.theapp == None and msg.startswith(theappPrefix):
            self.theapp = msg[len(theappPrefix):]
            #print "self.theapp " + repr(self.theapp)
        if msg.find("FRC") != -1:
            self.FRClines.append(msgLF)
        if msg == "Not expected to hang":
            self.expectedToHang = False
        if msg == "Not expected to leak":
            self.expectedToLeak = False
        if msg == "Allowed to render inconsistently" or msg.find("nscoord_MAX") != -1 or msg.find("nscoord_MIN") != -1:
            self.expectedToRenderInconsistently = True
        if msg.startswith("Rendered inconsistently") and not self.expectedToRenderInconsistently and self.nsassertionCount == 0:
            # Ignoring testcases with assertion failures (or nscoord_MAX warnings) because of bug 575011 and bug 265084, more or less.
            self.fuzzerComplained = True
            self.printAndLog("@@@ " + msg)
        if msg.startswith("Leaked until "):
            self.sawOMGLEAK = True
            self.printAndLog("@@@ " + msg)
        if msg.startswith("FAILURE:"):
            self.fuzzerComplained = True
            self.printAndLog("@@@ " + msg)
        if msg.find("###!!! ASSERTION") != -1:
            self.nsassertionCount += 1
            if msg.find("Foreground URLs are active") != -1 or msg.find("Entry added to loadgroup twice") != -1:
                print "Ignoring memory leaks (bug 622315)" # testcase in comment 2
                self.expectedToLeak = True
            if self.nsassertionCount == 100:
                print "domInteresting.py: not considering it a failure if browser hangs, because assertions are slow with stack-printing on. Please test in opt builds too, or fix the assertion bugs."
                self.expectedToHang = True

        # It might be sensible to push more of this logic into detect_assertions...
        # cx->isExceptionPending() assertion is here because of bug 709954 and maybe bug 632239
        # jsfunfuzz needs this out of assertions.txt to try and get a testcase.
        newAssertion = detect_assertions.scanLine(self.knownPath, msgLF) and \
            not ("cx->isExceptionPending()" in msg) and \
            not ("Tear-off objects remain in hashtable at shutdown" in msg and (self.expectedToLeak or isWin))
        fatalAssertion = msg.startswith("###!!! ABORT") or msg.startswith("Assertion fail")

        if newAssertion:
            self.newAssertionFailure = True
            self.printAndLog("@@@ " + msg)
        if fatalAssertion:
            self.sawFatalAssertion = True
            self.expectedToLeak = True # bug 763182
            overlyGenericAssertion = ("You can't dereference a NULL" in msg)
            if not overlyGenericAssertion:
                self.crashIsKnown = True

        if not self.mallocFailure and detect_malloc_errors.scanLine(msgLF):
            self.mallocFailure = True
            self.printAndLog("@@@ Malloc is unhappy")
        if self.valgrind and valgrindComplaintRegexp.match(msg):
            if not self.sawValgrindComplaint:
                self.sawValgrindComplaint = True
                self.printAndLog("@@@ First Valgrind complaint")
            if len(self.summaryLog) < 100:
                self.summaryLog.append(msgLF)
        if (msg.startswith("TEST-UNEXPECTED-FAIL | automation.py | application timed out") or
           msg.startswith("TEST-UNEXPECTED-FAIL | automation.py | application ran for longer")):
            self.timedOut = True
            self.crashIsKnown = True

        if msg == "PROCESS-CRASH | automation.py | application crashed (minidump found)":
            print "We have a crash on our hands!"
            self.crashProcessor = "minidump_stackwalk"
        if "ERROR: AddressSanitizer" in msg:
            print "We have an asan crash on our hands!"
            self.crashProcessor = "asan"
            if "failed to allocate" in msg:
                self.crashIsKnown = True

        if msg.startswith("freed by thread") or msg.startswith("previously allocated by thread"):
            # We don't want to treat these as part of the stack trace for the purpose of detect_interesting_crashes.
            self.crashBoringBits = True

        if self.crashProcessor and len(self.summaryLog) < 300:
            self.summaryLog.append(msgLF)
        if self.crashProcessor and not self.crashBoringBits and detect_interesting_crashes.isKnownCrashSignature(msg):
            self.printAndLog("%%% Known crash signature: " + msg)
            self.crashIsKnown = True

        if isMac:
            # There are several [TMR] bugs listed in crashes.txt
            # Bug 507876 is a breakpad issue that means too-much-recursion crashes don't give me stack traces on Mac
            # (and Linux, but differently).
            # The combination means we lose.
            if (msg.startswith("Crash address: 0xffffffffbf7ff") or msg.startswith("Crash address: 0x5f3fff")):
                self.printAndLog("%%% This crash is at the Mac stack guard page. It is probably a too-much-recursion crash or a stack buffer overflow.")
                self.crashMightBeTooMuchRecursion = True
            if self.crashMightBeTooMuchRecursion and msg.startswith(" 3 "):
                self.printAndLog("%%% The stack trace is not broken, so it's more likely to be a stack buffer overflow.")
                self.crashMightBeTooMuchRecursion = False
            if self.crashMightBeTooMuchRecursion and msg.startswith("Thread 1"):
                self.printAndLog("%%% The stack trace is broken, so it's more likely to be a too-much-recursion crash.")
                self.crashIsKnown = True
            if msg.endswith(".dmp has no thread list"):
                self.printAndLog("%%% This crash report is totally busted. Giving up.")
                self.crashIsKnown = True

        if ("quitApplication" in msg or
            "fuzzerWhenDeep" in msg or # Bug 732665
            "InternalError: too much recursion" in msg # Bug 732665 (see bug 762598 for a testcase)
            ):
            self.expectChromeFailure = True
        if (not self.expectChromeFailure and
            (msg.find("uncaught exception") != -1 or msg.find("JavaScript error") != -1 or msg.find("JavaScript Error") != -1) and
            (msg.find("chrome://browser/") != -1 or msg.find("resource:///components") != -1) and
             msg.find("nsIWebProgress.DOMWindow") == -1 and # bug 732593
             msg.find("installStatus is null") == -1 and # bug 693237
             msg.find("aTab is null") == -1 and # bug 693239
             msg.find("too much recursion") == -1 and # bug 732665
             msg.find("nsIWebContentHandlerRegistrar::registerProtocolHandler") == -1 and # bug 732692, bug 693270
             msg.find("nsIWebContentHandlerRegistrar::registerContentHandler") == -1 and # bug 732692, bug 693270
             msg.find("iconStatus is null") == -1 and # bug 733305
             msg.find("prompt aborted by user") == -1 and # thrown intentionally in nsPrompter.js
             msg.find("nsIIOService.getProtocolHandler") == -1 and # bug 746878
             msg.find("tipElement is null") == -1 # bug 746893
            ):
            self.printAndLog("@@@ " + msg)
            self.sawChromeFailure = True

        return msgLF
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
            # browserDir is a downloaded packaged build, perhaps downloaded with downloadBuild.py.  Great!
            #self.appDir = os.path.join(browserDir, "dist")
            self.reftestFilesDir = os.path.join(browserDir, "tests", "reftest", "tests")
            self.reftestScriptDir = os.path.join(browserDir, "tests", "reftest")
            self.utilityDir = os.path.join(browserDir, "tests", "bin")
            self.symbolsDir = os.path.join(browserDir, "symbols")
            possible_stackwalk_fn = "minidump_stackwalk.exe" if isWin else "minidump_stackwalk"
            possible_stackwalk = os.path.join(browserDir, possible_stackwalk_fn)
            if (not os.environ.get('MINIDUMP_STACKWALK', None) and
                not os.environ.get('MINIDUMP_STACKWALK_CGI', None) and
                os.path.exists(possible_stackwalk)):
                self.stackwalk = possible_stackwalk
        elif os.path.exists(os.path.join(browserDir, "dist")) and os.path.exists(os.path.join(browserDir, "_tests")):
            # browserDir is an objdir (more convenient for local builds)
            #self.appDir = browserDir
            self.reftestFilesDir = findSrcDir(browserDir)
            self.reftestScriptDir = os.path.join(browserDir, "_tests", "reftest")
            self.utilityDir = os.path.join(browserDir, "dist", "bin")  # on mac, looking inside the app would also work!
            self.symbolsDir = os.path.join(browserDir, "dist", "crashreporter-symbols")
        else:
            raise Exception("browserDir should be an objdir for a local build, or a Tinderbox build downloaded with downloadBuild.py")

        #if not os.path.exists(self.appDir):
        #  raise Exception("Oops! appDir does not exist!")
        if not os.path.exists(self.reftestScriptDir):
            raise Exception("Oops! reftestScriptDir does not exist! " + self.reftestScriptDir)
        if not os.path.exists(self.reftestFilesDir):
            raise Exception("Oops! reftestFilesDir does not exist! " + self.reftestFilesDir)
        if not os.path.exists(self.utilityDir):
            raise Exception("Oops! utilityDir does not exist!" + self.utilityDir)

        if not os.path.exists(self.symbolsDir):
            self.symbolsDir = None
        if self.symbolsDir:
            self.symbolsDir = getFullPath(self.symbolsDir)

def findSrcDir(objDir):
    with open(os.path.join(objDir, "Makefile")) as f:
        for line in f:
            if line.startswith("topsrcdir"):
                return deCygPath(line.split("=", 1)[1].strip())

    raise Exception("Didn't find a topsrcdir line in the Makefile")

def deCygPath(p):
    """Convert a cygwin-style path to a native Windows path"""
    if isWin and p.startswith("/c/"):
        p = "c:\\" + p.replace("/", "\\")[3:]
    return p

def grabExtraPrefs(p):
    basename = os.path.basename(p)
    if os.path.exists(p):
        hyphen = basename.find("-")
        if hyphen != -1:
            prefsFile = os.path.join(os.path.dirname(p), basename[0:hyphen] + "-prefs.txt")
            print "Looking for prefsFile: " + prefsFile
            if os.path.exists(prefsFile):
                print "Found prefs.txt"
                with open(prefsFile) as f:
                    return f.read()
    return ""


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

    # Standalone domInteresting:  Optional. Load this URL or file (rather than the Bugzilla front page)
    # loopdomfuzz:                Optional. Test (and possibly splice/reduce) only this URL, rather than looping (but note the prefs file isn't maintained)
    # Lithium:                    Required. Reduce this file.
    options.argURL = args[1] if len(args) > 1 else ""

    options.browserDir = browserDir # used by loopdomfuzz

    profileDir = mkdtemp(prefix="domfuzz-rdf-profile")
    createDOMFuzzProfile(profileDir)

    runBrowserOptions = []
    if dirs.symbolsDir:
        runBrowserOptions.append("--symbols-dir=" + dirs.symbolsDir)

    env = os.environ.copy()
    env['REFTEST_FILES_DIR'] = dirs.reftestFilesDir
    if dirs.stackwalk:
        env['MINIDUMP_STACKWALK'] = dirs.stackwalk
    runBrowserArgs = [dirs.reftestScriptDir, dirs.utilityDir, profileDir]
    runbrowserpy = ["python", "-u", os.path.join(THIS_SCRIPT_DIRECTORY, "runbrowser.py")]

    close_fds = sys.platform != 'win32'

    knownPath = os.path.join(THIS_SCRIPT_DIRECTORY, os.pardir, os.pardir, "known", "mozilla-central")
    detect_interesting_crashes.readIgnoreLists(knownPath)

    if options.valgrind:
        runBrowserOptions.append("--valgrind")
        runBrowserOptions.append("--vgargs="
          "--error-exitcode=" + str(VALGRIND_ERROR_EXIT_CODE) + " " +
          "--suppressions=" + os.path.join(knownPath, "valgrind.txt") + " " +
          "--gen-suppressions=all" + " " +
          "--child-silent-after-fork=yes" + " " + # First part of the workaround for bug 658840
    #      "--leak-check=full" + " " +
          "--smc-check=all-non-file" + " " +
    #      "--track-origins=yes" + " " +
    #      "--num-callers=50" + " " +
          "--quiet"
        )

    def deleteProfile():
        if profileDir:
            print "Deleting Firefox profile in " + profileDir
            shutil.rmtree(profileDir)

    def levelAndLines(url, logPrefix=None, extraPrefs=""):
        """Run Firefox using the profile created above, detecting bugs and stuff."""

        writePrefs(profileDir, extraPrefs)

        localstoreRDF = os.path.join(profileDir, "localstore.rdf")
        if os.path.exists(localstoreRDF):
            os.remove(localstoreRDF)

        leakLogFile = logPrefix + "-leaks.txt"

        runbrowser = subprocess.Popen(
                         runbrowserpy + ["--leak-log-file=" + leakLogFile] + runBrowserOptions + runBrowserArgs + [url],
                         stdin = None,
                         stdout = subprocess.PIPE,
                         stderr = subprocess.STDOUT,
                         env = env,
                         close_fds = close_fds)

        alh = AmissLogHandler(knownPath)
        alh.valgrind = options.valgrind

        # Bug 718208
        if extraPrefs.find("inflation") != -1:
            alh.expectedToRenderInconsistently = True

        statusLinePrefix = "RUNBROWSER INFO | runbrowser.py | runApp: exited with status "
        status = -9000

        # NB: not using 'for line in runbrowser.stdout' because that uses a hidden buffer
        # see http://docs.python.org/library/stdtypes.html#file.next
        while True:
            line = runbrowser.stdout.readline()
            if line != '':
                line = alh.processLine(line)
                print line,
                if line.startswith(statusLinePrefix):
                    status = int(line[len(statusLinePrefix):])
            else:
                break

        lev = DOM_FINE

        if alh.newAssertionFailure:
            lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)
        if alh.mallocFailure:
            lev = max(lev, DOM_MALLOC_ERROR)
        if alh.fuzzerComplained or alh.sawChromeFailure:
            lev = max(lev, DOM_FUZZER_COMPLAINED)
        if alh.sawValgrindComplaint:
            lev = max(lev, DOM_VG_AMISS)

        if alh.timedOut:
            if alh.expectedToHang or options.valgrind:
                alh.printAndLog("%%% An expected hang")
            else:
                alh.printAndLog("@@@ Unexpected hang")
                lev = max(lev, DOM_TIMED_OUT_UNEXPECTEDLY)
        elif alh.crashProcessor:
            if alh.crashIsKnown:
                alh.printAndLog("%%% Known crash (from " + alh.crashProcessor + ")")
            else:
                alh.printAndLog("@@@ New crash (from " + alh.crashProcessor + ")")
                lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)
        elif options.valgrind and status == VALGRIND_ERROR_EXIT_CODE:
            # Disabled due to leaks in the glxtest process that Firefox forks on Linux.
            # (Second part of the workaround for bug 658840.)
            # (We detect Valgrind warnings as they happen, instead.)
            #alh.printAndLog("@@@ Valgrind complained via exit code")
            #lev = max(lev, DOM_VG_AMISS)
            pass
        elif status < 0 and os.name == 'posix':
            # The program was terminated by a signal, which usually indicates a crash.
            signum = -status
            signame = getSignalName(signum, "unknown signal")
            print("DOMFUZZ INFO | domInteresting.py | Terminated by signal " + str(signum) + " (" + signame + ")")
            if isMac and signum != signal.SIGKILL and signum != signal.SIGTERM and not alh.crashProcessor:
                # well, maybe the OS crash reporter picked it up.
                crashlog = grabCrashLog(os.path.basename(alh.theapp), alh.theapp, alh.pid, None)
                if crashlog:
                    with open(crashlog) as f:
                        crashText = f.read()
                    print crashText
                    if not (" main + " in crashText or " XRE_main + " in crashText or " exit + " in crashText):
                        # e.g. this build only has breakpad symbols, not native symbols
                        alh.printAndLog("%%% Busted crash report (from mac crash reporter)")
                    elif alh.crashIsKnown:
                        alh.printAndLog("%%% Ignoring crash report (from mac crash reporter)")
                    elif detect_interesting_crashes.amiss(knownPath, crashlog, True):
                        alh.printAndLog("@@@ New crash (from mac crash reporter)")
                        if logPrefix:
                            shutil.copyfile(crashlog, logPrefix + "-crash.txt")
                        lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)
                    else:
                        alh.printAndLog("%%% Known crash (from mac crash reporter)")
        elif status == 1:
            alh.printAndLog("@@@ Exited with status 1 -- OOM?")
        elif status != 0 and not (isWin and alh.sawFatalAssertion):
            alh.printAndLog("@@@ Abnormal exit (status %d)" % status)
            lev = max(lev, DOM_ABNORMAL_EXIT)

        if os.path.exists(leakLogFile) and status == 0 and detect_leaks.amiss(knownPath, leakLogFile, verbose=True) and not alh.expectedToLeak:
            alh.printAndLog("@@@ Unexpected leak or leak pattern")
            alh.printAndLog("Leak details: " + os.path.basename(leakLogFile))
            lev = max(lev, DOM_NEW_LEAK)
        else:
            if alh.sawOMGLEAK and not alh.expectedToLeak:
                lev = max(lev, DOM_NEW_LEAK)
            if leakLogFile:
                # Remove the main leak log file, plus any plugin-process leak log files
                for f in glob.glob(leakLogFile + "*"):
                    os.remove(f)


        if (lev > DOM_FINE) and logPrefix:
            with open(logPrefix + "-output.txt", "w") as outlog:
                outlog.writelines(alh.fullLogHead)
            subprocess.call(["gzip", logPrefix + "-output.txt"])
            with open(logPrefix + "-summary.txt", "w") as summaryLogFile:
                summaryLogFile.writelines(alh.summaryLog)

        print("DOMFUZZ INFO | domInteresting.py | Running for fuzzage, level " + str(lev) + ".")

        FRClines = alh.FRClines

        return (lev, FRClines)

    return levelAndLines, deleteProfile, options # return a closure along with the set of options

# For use by Lithium
def init(args):
    global levelAndLinesForLithium, deleteProfileForLithium, minimumInterestingLevel, lithiumURL, extraPrefsForLithium
    levelAndLinesForLithium, deleteProfileForLithium, options = rdfInit(args)
    minimumInterestingLevel = options.minimumInterestingLevel
    lithiumURL = options.argURL
def interesting(args, tempPrefix):
    extraPrefs = grabExtraPrefs(lithiumURL) # Here in case Lithium is reducing the prefs file
    actualLevel, lines = levelAndLinesForLithium(lithiumURL, logPrefix = tempPrefix, extraPrefs = extraPrefs)
    return actualLevel >= minimumInterestingLevel
def cleanup(args):
    # we don't get to try..finally for Ctrl+C.
    # could this be fixed by using a generator with yield?
    deleteProfileForLithium()

# For direct (usually manual) invocations
def directMain():
    logPrefix = os.path.join(mkdtemp(prefix="domfuzz-rdf-main"), "t")
    print logPrefix
    levelAndLines, deleteProfileForMain, options = rdfInit(sys.argv[1:])
    if options.argURL:
        extraPrefs = grabExtraPrefs(options.argURL)
    else:
        extraPrefs = ""
    level, lines = levelAndLines(options.argURL or "https://bugzilla.mozilla.org/", logPrefix, extraPrefs = extraPrefs)
    print level
    sys.exit(level)
    #deleteProfileForMain()

if __name__ == "__main__":
    directMain()

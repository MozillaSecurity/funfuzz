#!/usr/bin/env python

"""

Runs Firefox with a fresh profile, with prefs appropriate for fuzzing or retesting fuzz bugs.
Identifies output that indicates that a bug has been found.

We run runbrowser.py through a (s)ubprocess.  runbrowser.py (i)mports automation.py.
This setup allows us to postprocess all automation.py output, including crash logs.

        i                  i                     s*                i                  s
bot.py --> loopdomfuzz.py --> domInteresting.py --> runbrowser.py --> automation.py+ --> firefox-bin
                                   ^
                                   |
                                   |
                              you are here

"""


import sys
import shutil
import os
import signal
import glob
import re
from optparse import OptionParser
from tempfile import mkdtemp
import subprocess

# could also use sys._getframe().f_code.co_filename, but this seems cleaner
THIS_SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
import randomPrefs

p1 = os.path.abspath(os.path.join(THIS_SCRIPT_DIRECTORY, os.pardir, os.pardir, 'detect'))
sys.path.insert(0, p1)
import detect_assertions
import detect_malloc_errors
import detect_crashes
import detect_leaks
import findIgnoreLists

path2 = os.path.abspath(os.path.join(THIS_SCRIPT_DIRECTORY, os.pardir, os.pardir, 'util'))
sys.path.append(path2)
import subprocesses as sps

close_fds = sys.platform != 'win32'

# Levels of unhappiness.
# These are in order from "most expected to least expected" rather than "most ok to worst".
# Fuzzing will note the level, and pass it to Lithium.
# Lithium is allowed to go to a higher level.
(
    DOM_FINE,
    DOM_TIMED_OUT_UNEXPECTEDLY,
    DOM_ABNORMAL_EXIT,
    DOM_FUZZER_COMPLAINED,
    DOM_VG_AMISS,
    DOM_NEW_LEAK,
    DOM_MALLOC_ERROR,
    DOM_NEW_ASSERT_OR_CRASH
) = range(8)

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
    prefsText = ""

    with open(os.path.join(THIS_SCRIPT_DIRECTORY, "constant-prefs.js")) as kPrefs:
        for line in kPrefs:
            prefsText += line

    prefsText += "\n"
    prefsText += "// Extra, random prefs\n"
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


valgrindComplaintRegexp = re.compile(r"^==\d+== ")


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
        self.timedOut = False
        self.goingDownHard = False
        self.sawValgrindComplaint = False
        self.expectChromeFailure = False
        self.sawChromeFailure = False

        self.crashWatcher = detect_crashes.CrashWatcher(knownPath, True, lambda note: self.printAndLog("%%% " + note))

    def processLine(self, msgLF):
        msgLF = stripBeeps(msgLF)
        msg = msgLF.rstrip("\n")

        self.crashWatcher.processOutputLine(msg)
        if self.crashWatcher.crashProcessor and len(self.summaryLog) < 300:
            self.summaryLog.append(msgLF)

        if len(self.fullLogHead) < 100000:
            self.fullLogHead.append(msgLF)
        pidprefix = "INFO | automation.py | Application pid:"
        if self.pid is None and msg.startswith(pidprefix):
            self.pid = int(msg[len(pidprefix):])
            #print "Firefox pid: " + str(self.pid)
        theappPrefix = "theapp: "
        if self.theapp is None and msg.startswith(theappPrefix):
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
        if "[object nsXPCComponents_Classes" in msg:
            # See 'escalationAttempt' in fuzzer-combined.js
            # A successful attempt will output something like:
            #   Release: [object nsXPCComponents_Classes]
            #   Debug: [object nsXPCComponents_Classes @ 0x12036b880 (native @ 0x1203678d0)]
            self.fuzzerComplained = True
            self.printAndLog("@@@ " + msg)

        if msg.find("###!!! ASSERTION") != -1:
            self.nsassertionCount += 1
            if msg.find("Foreground URLs are active") != -1 or msg.find("Entry added to loadgroup twice") != -1:
                # print "Ignoring memory leaks (bug 622315)"  # testcase in comment 2
                self.expectedToLeak = True
            if "nsCARenderer::Render failure" in msg:
                # print "Ignoring memory leaks (bug 840688)"
                self.expectedToLeak = True
            if "ASSERTION: Appshell already destroyed" in msg:
                # print "Ignoring memory leaks (bug 933730)"
                self.expectedToLeak = True
            if "Did not receive all required callbacks" in msg:
                # print "Ignoring memory leaks (bug 973384)"
                self.expectedToLeak = True
            if "leaking" in msg:
                # print "Ignoring memory leaks"
                self.expectedToLeak = True
            if self.nsassertionCount == 100:
                # print "domInteresting.py: not considering it a failure if browser hangs, because assertions are slow with stack-printing on. Please test in opt builds too, or fix the assertion bugs."
                self.expectedToHang = True

        assertionSeverity, newAssertion = detect_assertions.scanLine(self.knownPath, msgLF)

        # Treat these fatal assertions as crashes. This lets us distinguish call sites and makes ASan signatures match.
        overlyGenericAssertion = (
            "You can't dereference a NULL" in msg or
            ("Assertion failure: false," in msg) or
            ("Assertion failure: value" in msg and "BindingUtils.h" in msg) or
            ("Assertion failure: i < Length() (invalid array index)" in msg)
        )

        newAssertion = newAssertion and (
            not overlyGenericAssertion and
            not (self.expectedToLeak and "ASSERTION: Component Manager being held past XPCOM shutdown" in msg) and
            not (self.expectedToLeak and "Tear-off objects remain in hashtable at shutdown" in msg) and
            not ("Assertion failed: _cairo_status_is_error" in msg and sps.isWin) and  # A frequent error that I cannot reproduce
            not ("JS_IsExceptionPending" in msg) and  # Bug 735081, bug 735082
            not (self.goingDownHard and sps.isWin) and  # Bug 763182
            True)

        if newAssertion:
            self.newAssertionFailure = True
            self.printAndLog("@@@ " + msg)
        if assertionSeverity == detect_assertions.FATAL_ASSERT:
            self.sawFatalAssertion = True
            self.goingDownHard = True
            if not overlyGenericAssertion:
                self.crashWatcher.crashIsKnown = True

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
                msg.startswith("TEST-UNEXPECTED-FAIL | automation.py | application ran for longer") or
                "Shutdown too long, probably frozen, causing a crash" in msg):
            # A hang was caught by either automation.py or by RunWatchdog (toolkit/components/terminator/nsTerminator.cpp)
            self.timedOut = True
            self.goingDownHard = True
            self.crashWatcher.crashIsKnown = True

        if "goQuitApplication" in msg:
            self.expectChromeFailure = True
        if "JavaScript error: self-hosted" in msg:
            # Bug 1186741: ignore this and future chrome failures
            self.expectChromeFailure = True
        if (not self.expectChromeFailure) and chromeFailure(msg) and not knownChromeFailure(msg):
            self.printAndLog("@@@ " + msg)
            self.sawChromeFailure = True

        return msgLF

    def printAndLog(self, msg):
        print "$ " + msg
        self.fullLogHead.append(msg + "\n")
        self.summaryLog.append(msg + "\n")


def chromeFailure(msg):
    """Look for strings that indicate failures in privileged Firefox code, as well as general JS failures from files we know are privileged."""
    return (
            #"A coding exception was thrown and uncaught in a Task" in msg or  # bug 1183435 || These are followed by stacks, which could be used to distinguish them...
            "System JS : ERROR" in msg or
            "JS Component Loader: ERROR" in msg or
            (generalJsFailure(msg) and jsInChrome(msg)))


def generalJsFailure(msg):
    return ("uncaught exception" in msg or
            "JavaScript error" in msg or
            "JavaScript Error" in msg or
            "[Exception..." in msg or
            "SyntaxError" in msg or
            "ReferenceError" in msg or
            "TypeError" in msg or
            False)


def jsInChrome(msg):
    return ("chrome://browser/" in msg or
            "chrome://global/content/bindings/browser.xml" in msg or
            "resource:///app/" in msg or
            "resource:///components" in msg or
            "resource:///modules/" in msg or
            "resource://app/" in msg or
            "resource://components" in msg or
            "resource://modules/" in msg or
            "resource://gre/modules/" in msg or
            "resource://gre/components/" in msg or
            "self-hosted" in msg or
            False) and not (
                "xbl-marquee.xml" in msg or  # chrome://xbl-marquee/content/xbl-marquee.xml
                "videocontrols.xml" in msg  # chrome://global/content/bindings/videocontrols.xml
            )


def knownChromeFailure(msg):
    return (
        "nsIWebProgress.DOMWindow" in msg or                                            # bug 732593
        "nsIWebProgress.isTopLevel" in msg or                                           # bug 732593
        "installStatus is null" in msg or                                               # bug 693237
        "aTab is null" in msg or                                                        # bug 693239
        "tab is null" in msg or                                                         # bug 693239?
        "browser is null" in msg or                                                     # bug 693239?
        "nsIWebContentHandlerRegistrar::registerProtocolHandler" in msg or              # bug 732692, bug 693270
        "nsIWebContentHandlerRegistrar::registerContentHandler" in msg or               # bug 732692, bug 693270
        "prompt aborted by user" in msg or                                              # thrown intentionally in nsPrompter.js
        "newPrompt.abortPrompt is not a function" in msg or                             # trying to do things after closing the window
        "nsIIOService.getProtocolHandler" in msg or                                     # bug 746878
        "tipElement is null" in msg or                                                  # bug 746893
        ("browser.xul" in msg and "gBrowserInit is not defined" in msg) or              # Bug 897867
        ("browser.js" in msg and "overlayText is null" in msg) or                       # Bug 797945
        ("browser.js" in msg and "organizer.PlacesOrganizer" in msg) or                 # Bug 801436?
        ("browser.js" in msg and "element is null" in msg) or                           # trustedKeyEvent can artifically direct F6 at browser.js (focusNextFrame) when the focused window is a Scratchpad window
        ("browser.js" in msg and "this.UIModule is undefined" in msg) or                # Bug 877013
        ("browser.js" in msg and "this._cps2 is undefined" in msg) or                   # Bug 877013
        ("browser.js" in msg and "this.button is null" in msg) or                       # Bug 877013
        ("browser.js" in msg and "PanelUI.panel is undefined" in msg) or                # Bug 1228793
        ("BrowserUtils.jsm" in msg and "NS_ERROR_MALFORMED_URI" in msg) or              # Bug 1187207
        ("nsSidebar.js" in msg and "NS_NOINTERFACE" in msg) or                          # Bug 1186365
        ("amInstallTrigger.js" in msg and "NS_ERROR_MALFORMED_URI" in msg) or           # Bug 1186694
        ("amInstallTrigger.js" in msg and "NS_NOINTERFACE" in msg) or                   # Bug 1230343
        ("browser.xml" in msg and "this.docShell is null" in msg) or                    # Bug 919362
        ("places.js" in msg and "PlacesUIUtils is not defined" in msg) or               # Bug 801436
        ("places.js" in msg and "this._places is null" in msg) or                       # Bug 893322
        ("pageInfo.js" in msg and "elem.ownerDocument.defaultView" in msg) or           # Bug 799329
        ("pageInfo.js" in msg and "can't access dead object" in msg) or                 # Bug 799329 ?
        ("pageInfo.js" in msg and "imgIRequest.image" in msg) or                        # Bug 801930
        ("pageInfo.js" in msg and "NS_ERROR_MALFORMED_URI" in msg) or                   # Bug 949927
        ("pageInfo.js" in msg and ": NS_ERROR_FAILURE" in msg) or                       # Bug 979400
        ("aboutHome.js" in msg and "The operation is insecure" in msg) or               # Bug 873300
        ("PermissionSettings.js" in msg and "aWindow.document is null" in msg) or       # Bug 927294
        ("nsDOMIdentity.js" in msg and "aWindow.document is null" in msg) or            # Bug 931286
        ("tabbrowser.xml" in msg and "b.webProgress is undefined" in msg) or            # Bug 927339
        ("ConsoleAPI.js" in msg and "can't access dead object" in msg) or               # Bug 931304
        ("webrtcUI.jsm" in msg and "NS_ERROR_OUT_OF_MEMORY" in msg) or                  # Seems legit: whenfixed-local/webrtc-js-oom/
        ("webrtcUI.jsm" in msg and ".WebrtcIndicator is undefined" in msg) or           # Bug 949920
        ("webrtcUI.jsm" in msg and "getBrowserForWindow" in msg) or                     # Bug 950327
        ("webrtcUI.jsm" in msg) or                                                      # Bug 973318
        ("FeedConverter.js" in msg and "NS_ERROR_MALFORMED_URI" in msg) or              # Bug 949926
        ("FeedConverter.js" in msg and "2152398858" in msg) or                          # Bug 1227496 testcase 2
        ("webappsUI_uninit" in msg and "nsIObserverService.removeObserver" in msg) or   # bug 978524
        ("LoginManagerParent.jsm" in msg and "this._recipeManager is null" in msg) or   # bug 1167872
        ("LoginManagerParent.jsm" in msg and "this._recipeManager.getRecipesForHost is null" in msg) or   # bug 1167872 plus ion-eager changing the message?
        ("nsDOMIdentity.js, line " in msg) or                                           # Intentional messages about misusing the API
        ("IdpSandbox.jsm, line " in msg) or                                             # Intentional messages about misusing the API
        "DOMIdentity.jsm" in msg or                                                     # Bug 973397, bug 973398
        "FxAccounts.jsm" in msg or                                                      # Intermittent errors on startup
        "abouthealth.js" in msg or                                                      # Bug 895113
        "WindowsPrefSync.jsm" in msg or                                                 # Bug 947581
        "nsIFeedWriter::close" in msg or                                                # Bug 813408
        "SidebarUtils is not defined" in msg or                                         # Bug 856250
        "this.keyManager_ is null" in msg or                                            # mostly happens when i manually quit during a fuzz run
        "pbu_privacyContextFromWindow" in msg or                                        # bug 931304 whenfixed 'pb'
        ("PeerConnection.js" in msg and "NS_ERROR_FAILURE" in msg) or                   # Bug 978617
        ("PeerConnection.js" in msg and "Illegal constructor" in msg) or                # Bug 1186698
        ("PeerConnection.js" in msg and "2152398858" in msg) or                         # Bug 1227496
        ("PeerConnection.js" in msg and "NS_ERROR_MALFORMED_URI" in msg) or             # Bug 1230930
        ("PeerConnection.js" in msg and "e is null" in msg) or                          # Bug 1230381
        ("PeerConnection.js" in msg and "e is undefined" in msg) or                     # Bug 1230381
        ("ProcessHangMonitor.jsm" in msg and "win.gBrowser is undefined" in msg) or     # Bug 1186702
        ("ProcessHangMonitor.jsm" in msg and "win.gBrowser is null" in msg) or          # Bug 1186702
        ("vtt.jsm" in msg and "result is undefined" in msg) or                          # Bug 1186742
        ("vtt.jsm" in msg and "navigator is not defined" in msg) or                     # Bug 1228721
        ("Webapps.js" in msg and "this._window.top is null" in msg) or                  # Bug 1186743
        ("Webapps.js" in msg and "aApp is null" in msg) or                              # Bug 1228795
        ("content.js" in msg and "reportSendingMsg is null" in msg) or                  # Bug 1186751
        ("nsPrompter.js" in msg and "openModalWindow on a hidden window" in msg) or     # Bug 1186727
        ("LoginManagerContent.jsm" in msg and "doc.documentElement is null" in msg) or  # Bug 1191948
        ("System JS : ERROR (null):0" in msg) or                                        # Bug 987048
        ("System JS" in msg) or                                                         # Bug 987222
        ("CSSUnprefixingService.js" in msg) or                                          # Code going away (bug 1213126?)
        ("PerformanceStats.jsm" in msg and ".isMonitoringJank" in msg) or               # Bug 1221761
        ("tab-content.js" in msg and "content is null" in msg) or                       # Bug 1230087
        ("MainProcessSingleton.js" in msg and "NS_ERROR_ILLEGAL_VALUE" in msg) or       # Bug 1230388
        ("content-sessionStore.js" in msg) or                                           # Bug 1195295 removes some broken code

        # opening dev tools while simultaneously opening and closing tabs is mean
        ("devtools/framework/toolbox.js" in msg and "container is null: TBOX_destroy" in msg) or
        ("browser.js" in msg and "gURLBar.editor is undefined" in msg) or
        ("browser.js" in msg and "browser is undefined" in msg) or
        ("browser.js" in msg and "gNavigatorBundle.getString is not a function" in msg) or
        ("browser.js" in msg and "gBrowser.browsers is undefined" in msg) or
        "devtools" in msg or  # most devtools js errors I hit are uninteresting races

        False
    )


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
            usage("browserDir does not exist: %s" % browserDir)

        if os.path.exists(os.path.join(browserDir, "dist")) and os.path.exists(os.path.join(browserDir, "tests")):
            # browserDir is a downloaded packaged build, perhaps downloaded with downloadBuild.py.  Great!
            #self.appDir = os.path.join(browserDir, "dist")
            self.reftestFilesDir = os.path.join(browserDir, "tests", "reftest", "tests")
            self.reftestScriptDir = os.path.join(browserDir, "tests", "reftest")
            self.utilityDir = os.path.join(browserDir, "tests", "bin")
            self.symbolsDir = os.path.join(browserDir, "symbols")
            possible_stackwalk_fn = "minidump_stackwalk.exe" if sps.isWin else "minidump_stackwalk"
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
            usage("browserDir does not appear to be a valid build: " + repr(browserDir))

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
    if sps.isWin and p.startswith("/c/"):
        p = "c:\\" + p.replace("/", "\\")[3:]
    return p


def removeIfExists(filename):
    if os.path.exists(filename):
        os.remove(filename)


def rdfInit(args):
    """
    Returns (levelAndLines, options).

    levelAndLines is a function that runs Firefox in a clean profile and analyzes Firefox's output for bugs.
    """

    parser = OptionParser(usage="%prog [options] browserDir [testcaseURL]")
    parser.add_option("--valgrind",
                      action="store_true", dest="valgrind",
                      default=False,
                      help="use valgrind with a reasonable set of options")
    parser.add_option("-m", "--minlevel",
                      type="int", dest="minimumInterestingLevel",
                      default=DOM_FINE + 1,
                      help="minimum domfuzz level for lithium to consider the testcase interesting")
    parser.add_option("--background",
                      action="store_true", dest="background",
                      default=False,
                      help="Run the browser in the background on Mac (e.g. for local reduction)")
    options, args = parser.parse_args(args)

    if len(args) < 1:
        usage("Missing browserDir argument")
    browserDir = args[0]
    dirs = FigureOutDirs(getFullPath(browserDir))

    # Standalone domInteresting:  Optional. Load this URL or file (rather than the Bugzilla front page)
    # loopdomfuzz:                Optional. Test (and possibly splice/reduce) only this URL, rather than looping (but note the prefs file isn't maintained)
    # Lithium:                    Required. Reduce this file.
    options.argURL = args[1] if len(args) > 1 else ""

    options.browserDir = browserDir  # used by loopdomfuzz

    runBrowserOptions = []
    if options.background:
        runBrowserOptions.append("--background")
    if dirs.symbolsDir:
        runBrowserOptions.append("--symbols-dir=" + dirs.symbolsDir)

    env = os.environ.copy()
    env['MOZ_FUZZING_SAFE'] = '1'
    env['REFTEST_FILES_DIR'] = dirs.reftestFilesDir
    env['ASAN_SYMBOLIZER_PATH'] = os.path.expanduser("~/llvm/build-release/bin/llvm-symbolizer")
    if dirs.stackwalk:
        env['MINIDUMP_STACKWALK'] = dirs.stackwalk
    runbrowserpy = [sys.executable, "-u", os.path.join(THIS_SCRIPT_DIRECTORY, "runbrowser.py")]

    knownPath = "mozilla-central"

    if options.valgrind:
        runBrowserOptions.append("--valgrind")

        suppressions = ""
        for suppressionsFile in findIgnoreLists.findIgnoreLists(knownPath, "valgrind.txt"):
            suppressions += "--suppressions=" + suppressionsFile + " "

        vgargs = (
            "--error-exitcode=" + str(VALGRIND_ERROR_EXIT_CODE) + " " +
            "--gen-suppressions=all" + " " +
            suppressions +
            "--child-silent-after-fork=yes" + " " +  # First part of the workaround for bug 658840
            # "--leak-check=full" + " " +
            # "--show-possibly-lost=no" + " " +
            "--smc-check=all-non-file" + " " +
            # "--track-origins=yes" + " " +
            # "--num-callers=50" + " " +
            "--quiet"
        )

        runBrowserOptions.append("--vgargs=" + vgargs)  # spaces are okay here

    def levelAndLines(url, logPrefix=None, extraPrefs="", quiet=False, leaveProfile=False):
        """Run Firefox using the profile created above, detecting bugs and stuff."""

        profileDir = mkdtemp(prefix="domfuzz-rdf-profile")
        createDOMFuzzProfile(profileDir)
        writePrefs(profileDir, extraPrefs)

        runBrowserArgs = [dirs.reftestScriptDir, dirs.utilityDir, profileDir]

        assert logPrefix  # :(
        leakLogFile = logPrefix + "-leaks.txt"

        runbrowser = subprocess.Popen(
            runbrowserpy + ["--leak-log-file=" + leakLogFile] + runBrowserOptions + runBrowserArgs + [url],
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            close_fds=close_fds
        )

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
                if not quiet:
                    print line,
                if line.startswith(statusLinePrefix):
                    status = int(line[len(statusLinePrefix):])
            else:
                break

        lev = DOM_FINE

        if status < 0 and os.name == 'posix':
            # The program was terminated by a signal, which usually indicates a crash.
            signum = -status
            if signum != signal.SIGKILL and signum != signal.SIGTERM and not alh.crashWatcher.crashProcessor:
                # We did not detect a breakpad/ASan crash in the output, but it looks like the process crashed.
                # Look for a core file (to feed to gdb) or log from the Mac crash reporter.
                wantStack = True
                assert alh.theapp
                crashLog = sps.grabCrashLog(alh.theapp, alh.pid, logPrefix, wantStack)
                if crashLog:
                    alh.crashWatcher.readCrashLog(crashLog)
                else:
                    alh.printAndLog("@@@ The browser crashed, but did not leave behind any crash information!")
                    lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)

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
        elif alh.crashWatcher.crashProcessor:
            if alh.crashWatcher.crashIsKnown:
                alh.printAndLog("%%% Known crash (from " + alh.crashWatcher.crashProcessor + ")" + alh.crashWatcher.crashSignature)
            else:
                alh.printAndLog("@@@ New crash (from " + alh.crashWatcher.crashProcessor + ")" + alh.crashWatcher.crashSignature)
                lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)
        elif options.valgrind and status == VALGRIND_ERROR_EXIT_CODE:
            # Disabled due to leaks in the glxtest process that Firefox forks on Linux.
            # (Second part of the workaround for bug 658840.)
            # (We detect Valgrind warnings as they happen, instead.)
            #alh.printAndLog("@@@ Valgrind complained via exit code")
            #lev = max(lev, DOM_VG_AMISS)
            pass
        elif status < 0 and os.name == 'posix':
            signame = getSignalName(signum, "unknown signal")
            print "DOMFUZZ INFO | domInteresting.py | Terminated by signal " + str(signum) + " (" + signame + ")"
        elif status == 1:
            alh.printAndLog("%%% Exited with status 1 (OOM or plugin crash?)")
        elif status == -2147483645 and sps.isWin:
            alh.printAndLog("%%% Exited with status -2147483645 (plugin issue, bug 867263?)")
        elif status != 0 and not (sps.isWin and alh.sawFatalAssertion):
            alh.printAndLog("@@@ Abnormal exit (status %d)" % status)
            lev = max(lev, DOM_ABNORMAL_EXIT)

        if 'user_pref("layers.use-deprecated-textures", true);' in extraPrefs:
            # Bug 933569
            # Doing the change *here* only works because this is a small leak that shouldn't affect the reads in alh
            alh.expectedToLeak = True

        if os.path.exists(leakLogFile) and status == 0 and detect_leaks.amiss(knownPath, leakLogFile, verbose=not quiet) and not alh.expectedToLeak:
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

        if (lev == DOM_FINE) and logPrefix:
            removeIfExists(logPrefix + "-core.gz")
            removeIfExists(logPrefix + "-crash.txt")

        if not leaveProfile:
            shutil.rmtree(profileDir)

        print "DOMFUZZ INFO | domInteresting.py | " + str(lev)
        return (lev, alh.FRClines)

    return levelAndLines, options  # return a closure along with the set of options


def usage(note):
    print note
    print "(browserDir should be an objdir for a local build, or a Tinderbox build downloaded with downloadBuild.py)"
    print
    sys.exit(2)


# For use by Lithium
def init(args):
    global levelAndLinesForLithium, deleteProfileForLithium, minimumInterestingLevel, lithiumURL, extraPrefsForLithium
    levelAndLinesForLithium, options = rdfInit(args)
    minimumInterestingLevel = options.minimumInterestingLevel
    lithiumURL = options.argURL
def interesting(args, tempPrefix):
    global levelAndLinesForLithium, deleteProfileForLithium, minimumInterestingLevel, lithiumURL, extraPrefsForLithium
    extraPrefs = randomPrefs.grabExtraPrefs(lithiumURL) # Re-scan testcase (and prefs file) in case Lithium changed them
    actualLevel, lines = levelAndLinesForLithium(lithiumURL, logPrefix=tempPrefix, extraPrefs=extraPrefs)
    return actualLevel >= minimumInterestingLevel


# For direct (usually manual) invocations
def directMain():
    logPrefix = os.path.join(mkdtemp(prefix="domfuzz-rdf-main"), "t")
    print logPrefix
    levelAndLines, options = rdfInit(sys.argv[1:])
    if options.argURL:
        extraPrefs = randomPrefs.grabExtraPrefs(options.argURL)
    else:
        extraPrefs = ""
    level, lines = levelAndLines(options.argURL or "about:blank", logPrefix, extraPrefs=extraPrefs, leaveProfile=True)
    print level
    sys.exit(level)


if __name__ == "__main__":
    directMain()

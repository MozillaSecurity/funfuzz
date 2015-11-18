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
import platform
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
import detect_leaks
import findIgnoreLists

path2 = os.path.abspath(os.path.join(THIS_SCRIPT_DIRECTORY, os.pardir, os.pardir, 'util'))
sys.path.append(path2)
import subprocesses as sps
import createCollector

# From FuzzManager (in sys.path thanks to import createCollector above)
import FTB.Signatures.CrashInfo as CrashInfo
from FTB.ProgramConfiguration import ProgramConfiguration

close_fds = sys.platform != 'win32'

DOMI_MARKER = "[Non-crash bug] "  # For FuzzManager/FTB/AssertionHelper.py

# Levels of unhappiness.
# These are in order from "most expected to least expected" rather than "most ok to worst".
# Fuzzing will note the level, and pass it to Lithium.
# Lithium is allowed to go to a higher level.
(
    DOM_FINE,
    DOM_UNEXPECTED_HANG,
    DOM_ABNORMAL_EXIT,
    DOM_FUZZER_COMPLAINED,
    DOM_VG_AMISS,
    DOM_UNEXPECTED_LEAK,
    DOM_NEW_ASSERT_OR_CRASH
) = range(7)

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
    def __init__(self, knownPath, valgrind):
        self.mallocFailure = False
        self.knownPath = knownPath
        self.valgrind = valgrind
        self.theapp = None
        self.pid = None
        self.fullLog = []
        self.summaryLog = []
        self.expectedToHang = True
        self.expectedToLeak = True
        self.expectedToRenderInconsistently = False
        self.sawOMGLEAK = False
        self.nsassertionCount = 0
        self.sawFatalAssertion = False
        self.fuzzerComplained = False
        self.timedOut = False
        self.sawValgrindComplaint = False
        self.expectChromeFailure = False
        self.sawChromeFailure = False
        self.sawNewNonfatalAssertion = False

    def processLine(self, msgLF):
        msgLF = stripBeeps(msgLF)
        if not self.timedOut:
            self.fullLog.append(msgLF)
        msg = msgLF.rstrip("\n")

        pidprefix = "INFO | automation.py | Application pid:"
        if self.pid is None and msg.startswith(pidprefix):
            self.pid = int(msg[len(pidprefix):])
        theappPrefix = "theapp: "
        if self.theapp is None and msg.startswith(theappPrefix):
            self.theapp = msg[len(theappPrefix):]
        if msg == "Not expected to hang":
            self.expectedToHang = False
        if msg == "Not expected to leak":
            self.expectedToLeak = False
        if msg == "Allowed to render inconsistently" or msg.find("nscoord_MAX") != -1 or msg.find("nscoord_MIN") != -1:
            self.expectedToRenderInconsistently = True
        if msg.startswith("Rendered inconsistently") and not self.expectedToRenderInconsistently and self.nsassertionCount == 0:
            # Ignoring testcases with assertion failures (or nscoord_MAX warnings) because of bug 575011 and bug 265084, more or less.
            self.fuzzerComplained = True
            self.printAndLog(DOMI_MARKER + msg)
        if msg.startswith("Leaked until "):
            self.sawOMGLEAK = True
            self.printAndLog(DOMI_MARKER + msg)
        if msg.startswith("FAILURE:"):
            self.fuzzerComplained = True
            self.printAndLog(DOMI_MARKER + msg)
        if "[object nsXPCComponents_Classes" in msg:
            # See 'escalationAttempt' in fuzzer-combined.js
            # A successful attempt will output something like:
            #   Release: [object nsXPCComponents_Classes]
            #   Debug: [object nsXPCComponents_Classes @ 0x12036b880 (native @ 0x1203678d0)]
            self.fuzzerComplained = True
            self.printAndLog(DOMI_MARKER + "nsXPCComponents_Classes")

        if msg.find("###!!! ASSERTION") != -1:
            self.nsassertionCount += 1
            newNonfatalAssertion = detect_assertions.scanLine(self.knownPath, msg)
            if newNonfatalAssertion and not (self.expectedToLeak and "ASSERTION: Component Manager being held past XPCOM shutdown" in msg):
                self.sawNewNonfatalAssertion = True
                self.printAndLog(DOMI_MARKER + newNonfatalAssertion)
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
                # print """domInteresting.py: not considering it a failure if browser hangs, because assertions
                # are slow with stack-printing on.
                # Please test in opt builds too, or fix the assertion bugs."""
                self.expectedToHang = True

        if not self.mallocFailure and detect_malloc_errors.scanLine(msgLF):
            self.mallocFailure = True
            self.printAndLog(DOMI_MARKER + "Malloc is unhappy")
        if self.valgrind and valgrindComplaintRegexp.match(msg):
            if not self.sawValgrindComplaint:
                self.sawValgrindComplaint = True
                self.printAndLog(DOMI_MARKER + "First Valgrind complaint")
            if len(self.summaryLog) < 100:
                self.summaryLog.append(msgLF)
        if (msg.startswith("TEST-UNEXPECTED-FAIL | automation.py | application timed out") or
                msg.startswith("TEST-UNEXPECTED-FAIL | automation.py | application ran for longer") or
                "Shutdown too long, probably frozen, causing a crash" in msg):
            # A hang was caught by either automation.py or by RunWatchdog (toolkit/components/terminator/nsTerminator.cpp)
            self.timedOut = True

        if "goQuitApplication" in msg:
            self.expectChromeFailure = True
        if "JavaScript error: self-hosted" in msg:
            # Bug 1186741: ignore this and future chrome failures
            self.expectChromeFailure = True
        if (not self.expectChromeFailure) and chromeFailure(msg) and not knownChromeFailure(msg):
            self.printAndLog(DOMI_MARKER + msg)
            self.sawChromeFailure = True

        return msgLF

    def printAndLog(self, msg):
        print "$ " + msg
        self.fullLog.append(msg + "\n")
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
        ("BrowserUtils.jsm" in msg and "NS_ERROR_MALFORMED_URI" in msg) or              # Bug 1187207
        ("downloads.js" in msg and "\"Cu\" is read-only" in msg) or                     # Bug 1175877
        ("tab-content.js" in msg and "content is null" in msg) or                       # Bug 1186346
        ("nsSidebar.js" in msg and "NS_NOINTERFACE" in msg) or                          # Bug 1186365
        ("amInstallTrigger.js" in msg and "NS_ERROR_MALFORMED_URI" in msg) or           # Bug 1186694
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
        ("webappsUI_uninit" in msg and "nsIObserverService.removeObserver" in msg) or   # bug 978524
        ("LoginManagerParent.jsm" in msg and "this._recipeManager is null" in msg) or   # bug 1167872
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
        ("PeerConnection.js" in msg and "not callable" in msg) or                       # Bug 1186696
        ("PeerConnection.js" in msg and "Illegal constructor" in msg) or                # Bug 1186698
        ("PeerConnectionIdp.jsm" in msg and "sdp is " in msg) or                        # Bug 1187206
        ("ProcessHangMonitor.jsm" in msg and "win.gBrowser is undefined" in msg) or     # Bug 1186702
        ("vtt.jsm" in msg and "result is undefined" in msg) or                          # Bug 1186742
        ("Webapps.js" in msg and "this._window.top is null" in msg) or                  # Bug 1186743
        ("content.js" in msg and "reportSendingMsg is null" in msg) or                  # Bug 1186751
        ("process-content.js" in msg and "EXPORTED_SYMBOLS is not an array" in msg) or  # Bug 1188169
        ("nsPrompter.js" in msg and "openModalWindow on a hidden window" in msg) or     # Bug 1186727
        ("LoginManagerContent.jsm" in msg and "doc.documentElement is null" in msg) or  # Bug 1191948
        ("System JS : ERROR (null):0" in msg) or                                        # Bug 987048
        ("System JS" in msg) or                                                         # Bug 987222
        ("self-hosted" in msg and "NS_ERROR" in msg) or                                 # Bug 1216682

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
            self.hgRev = downloadedBuildRev(browserDir)
        elif os.path.exists(os.path.join(browserDir, "dist")) and os.path.exists(os.path.join(browserDir, "_tests")):
            # browserDir is an objdir (more convenient for local builds)
            #self.appDir = browserDir
            self.reftestFilesDir = findSrcDir(browserDir)
            self.reftestScriptDir = os.path.join(browserDir, "_tests", "reftest")
            self.utilityDir = os.path.join(browserDir, "dist", "bin")  # on mac, looking inside the app would also work!
            self.symbolsDir = os.path.join(browserDir, "dist", "crashreporter-symbols")
            self.hgRev = hgRepoRev(findSrcDir(browserDir))  # welcome to assumptionville
        else:
            usage("browserDir does not appear to be a valid build: " + repr(browserDir))

        print "hgRev = " + self.hgRev

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


def hgRepoRev(repoDir):
    return subprocess.check_output(['hg', '-R', repoDir, 'log', '-r', '.', '--template', '{node|short}'])


def downloadedBuildRev(browserDir):
    downloadDir = os.path.join(browserDir, "download")
    for fn in os.listdir(downloadDir):
        if fn.startswith("firefox-") and fn.endswith(".txt"):
            with open(os.path.join(downloadDir, fn)) as f:
                _buildId = f.readline()
                hgURL = f.readline()
                return hgURL.split("/")[-1][0:12]
            raise Exception("Missing rev in file")
    return Exception("Missing file with rev")


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


class BrowserConfig:

    def __init__(self, args, collector):
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

        # Standalone domInteresting:  Optional. Load this URL or file (rather than the Bugzilla front page)
        # loopdomfuzz:                Optional. Test (and possibly splice/reduce) only this URL, rather than looping (but note the prefs file isn't maintained)
        # Lithium:                    Required. Reduce this file.
        options.argURL = args[1] if len(args) > 1 else ""
        options.browserDir = browserDir  # used by loopdomfuzz

        self.dirs = FigureOutDirs(getFullPath(browserDir))
        self.options = options
        self.env = self.initEnv()
        self.knownPath = "mozilla-central"
        self.collector = collector
        self.runBrowserOptions = self.initRunBrowserOptions()
        self.pc = createProgramConfiguration(self.dirs.hgRev, None)

    def initEnv(self):
        env = os.environ.copy()
        env['MOZ_FUZZING_SAFE'] = '1'
        env['REFTEST_FILES_DIR'] = self.dirs.reftestFilesDir
        env['ASAN_SYMBOLIZER_PATH'] = os.path.expanduser("~/llvm/build/Release/bin/llvm-symbolizer")
        if self.dirs.stackwalk:
            env['MINIDUMP_STACKWALK'] = self.dirs.stackwalk
        return env

    def initRunBrowserOptions(self):
        runBrowserOptions = []
        if self.options.background:
            runBrowserOptions.append("--background")
        if self.dirs.symbolsDir:
            runBrowserOptions.append("--symbols-dir=" + self.dirs.symbolsDir)

        if self.options.valgrind:
            runBrowserOptions.append("--valgrind")

            suppressions = ""
            for suppressionsFile in findIgnoreLists.findIgnoreLists(self.knownPath, "valgrind.txt"):
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

        return runBrowserOptions



class BrowserResult:

    def __init__(self, cfg, url, logPrefix, extraPrefs="", quiet=False, leaveProfile=False):
        """Run Firefox once, detect bugs, and determine a 'level' based on the most severe unknown bug."""

        profileDir = mkdtemp(prefix="domfuzz-rdf-profile")
        createDOMFuzzProfile(profileDir)
        writePrefs(profileDir, extraPrefs)

        runBrowserArgs = [cfg.dirs.reftestScriptDir, cfg.dirs.utilityDir, profileDir]

        assert logPrefix  # :(
        leakLogFile = logPrefix + "-leaks.txt"

        runbrowserpy = [sys.executable, "-u", os.path.join(THIS_SCRIPT_DIRECTORY, "runbrowser.py")]
        runbrowser = subprocess.Popen(
            runbrowserpy + ["--leak-log-file=" + leakLogFile] + cfg.runBrowserOptions + runBrowserArgs + [url],
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Hmm, CrashInfo.fromRawCrashData expects them separate, but I like them together...
            env=cfg.env,
            close_fds=close_fds
        )

        alh = AmissLogHandler(cfg.knownPath, cfg.options.valgrind)

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

        if alh.mallocFailure:
            lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)
        if alh.fuzzerComplained or alh.sawChromeFailure:
            lev = max(lev, DOM_FUZZER_COMPLAINED)
        if alh.sawValgrindComplaint:
            lev = max(lev, DOM_VG_AMISS)
        if alh.sawNewNonfatalAssertion:
            lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)

        # Leak stuff
        if 'user_pref("layers.use-deprecated-textures", true);' in extraPrefs:
            # Bug 933569
            # Doing the change *here* only works because this is a small leak that shouldn't affect the reads in alh
            alh.expectedToLeak = True
        if os.path.exists(leakLogFile) and status == 0 and detect_leaks.amiss(cfg.knownPath, leakLogFile, verbose=not quiet) and not alh.expectedToLeak:
            alh.printAndLog(DOMI_MARKER + "Leak (trace-refcnt)")
            alh.printAndLog("Leak details: " + os.path.basename(leakLogFile))
            lev = max(lev, DOM_UNEXPECTED_LEAK)
        else:
            if alh.sawOMGLEAK and not alh.expectedToLeak:
                lev = max(lev, DOM_UNEXPECTED_LEAK)
            if leakLogFile:
                # Remove the main leak log file, plus any plugin-process leak log files
                for f in glob.glob(leakLogFile + "*"):
                    os.remove(f)

        # Do various stuff based on how the process exited
        if alh.timedOut:
            if alh.expectedToHang or cfg.options.valgrind:
                alh.printAndLog("%%% An expected hang")
            else:
                alh.printAndLog(DOMI_MARKER + "Unexpected hang")
                lev = max(lev, DOM_UNEXPECTED_HANG)
        elif status < 0 and os.name == 'posix':
            signum = -status
            signame = getSignalName(signum, "unknown signal")
            print "DOMFUZZ INFO | domInteresting.py | Terminated by signal " + str(signum) + " (" + signame + ")"
        elif status == 1:
            alh.printAndLog("%%% Exited with status 1 (crash?)")
        elif status == -2147483645 and sps.isWin:
            alh.printAndLog("%%% Exited with status -2147483645 (plugin issue, bug 867263?)")
        elif status != 0:
            alh.printAndLog(DOMI_MARKER + "Abnormal exit (status %d)" % status)
            lev = max(lev, DOM_ABNORMAL_EXIT)

        # Always look for crash information in stderr.
        linesWithoutLineBreaks = [s.rstrip() for s in alh.fullLog]
        crashInfo = CrashInfo.CrashInfo.fromRawCrashData([], linesWithoutLineBreaks, cfg.pc)

        # If the program crashed but we didn't find crash info in stderr (breakpad/asan),
        # poll for a core file (to feed to gdb) or log from the Mac crash reporter.
        if isinstance(crashInfo, CrashInfo.NoCrashInfo) and status < 0 and os.name == 'posix':
            signum = -status
            if signum != signal.SIGKILL and signum != signal.SIGTERM:
                wantStack = True
                assert alh.theapp
                crashLog = sps.grabCrashLog(alh.theapp, alh.pid, logPrefix, wantStack)
                if crashLog:
                    with open(crashLog) as f:
                        auxCrashData = f.readlines()
                    crashInfo = CrashInfo.CrashInfo.fromRawCrashData([], linesWithoutLineBreaks, cfg.pc, auxCrashData=auxCrashData)
                else:
                    alh.printAndLog(DOMI_MARKER + "The browser crashed, but did not leave behind any crash information!")
                    lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)

        createCollector.printCrashInfo(crashInfo)
        if not isinstance(crashInfo, CrashInfo.NoCrashInfo):
            lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)

        match = cfg.collector.search(crashInfo)
        if match[0] is not None:
            createCollector.printMatchingSignature(match)
            lev = DOM_FINE

        if lev > DOM_FINE:
            with open(logPrefix + "-output.txt", "w") as outlog:
                outlog.writelines(alh.fullLog)
            subprocess.call(["gzip", logPrefix + "-output.txt"])
            with open(logPrefix + "-summary.txt", "w") as summaryLogFile:
                summaryLogFile.writelines(alh.summaryLog)

        if lev == DOM_FINE:
            removeIfExists(logPrefix + "-core.gz")
            removeIfExists(logPrefix + "-crash.txt")

        if not leaveProfile:
            shutil.rmtree(profileDir)

        print "DOMFUZZ INFO | domInteresting.py | " + str(lev)

        self.level = lev
        self.lines = alh.fullLog
        self.crashInfo = crashInfo


def usage(note):
    print note
    print "(browserDir should be an objdir for a local build, or a Tinderbox build downloaded with downloadBuild.py)"
    print
    sys.exit(2)


def createProgramConfiguration(hgRev, args):
    s = platform.system()
    if s == "Darwin":
        osname = "macosx"
        is64 = platform.architecture()[0] == "64bit"
    elif s == "Linux":
        osname = "linux"
        is64 = platform.machine() == "x86_64"
    elif s == 'Windows':
        osname = "windows"
        is64 = False
    else:
        raise Exception("Unknown platform.system(): " + s)

    return ProgramConfiguration(
        "mozilla-central",
        "x86-64" if is64 else "x86",
        osname,
        hgRev,
        args=args
    )


# For use by Lithium
def init(args):
    global bcForLithium
    bcForLithium = BrowserConfig(args, createCollector.createCollector("DOMFuzz"))
def interesting(args, tempPrefix):
    global bcForLithium
    bc = bcForLithium
    url = bc.options.argURL
    extraPrefs = randomPrefs.grabExtraPrefs(url)  # Re-scan testcase (and prefs file) in case Lithium changed them
    br = BrowserResult(bc, url, tempPrefix, extraPrefs=extraPrefs)
    return br.level >= bc.options.minimumInterestingLevel


# For direct (usually manual) invocations
def directMain():
    logPrefix = os.path.join(mkdtemp(prefix="domfuzz-rdf-main"), "t")
    print logPrefix
    bc = BrowserConfig(sys.argv[1:], createCollector.createCollector("DOMFuzz"))
    if bc.options.argURL:
        extraPrefs = randomPrefs.grabExtraPrefs(bc.options.argURL)
    else:
        extraPrefs = ""
    br = BrowserResult(bc, bc.options.argURL or "about:blank", logPrefix, extraPrefs=extraPrefs, leaveProfile=True)
    print br.level
    sys.exit(br.level)


if __name__ == "__main__":
    directMain()

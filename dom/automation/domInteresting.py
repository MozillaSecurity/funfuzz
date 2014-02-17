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

close_fds = sys.platform != 'win32'

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
        self.crashIsExploitable = False
        self.timedOut = False
        self.goingDownHard = False
        self.sawValgrindComplaint = False
        self.expectChromeFailure = False
        self.sawChromeFailure = False
        self.outOfMemory = False
        detect_interesting_crashes.resetCounts()
        self.crashSignature = ""

    def processLine(self, msgLF):
        msgLF = stripBeeps(msgLF)
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
                print "Ignoring memory leaks (bug 622315)" # testcase in comment 2
                self.expectedToLeak = True
            if "nsCARenderer::Render failure" in msg:
                print "Ignoring memory leaks (bug 840688)"
                self.expectedToLeak = True
            if "ASSERTION: Appshell already destroyed" in msg:
                print "Ignoring memory leaks (bug 933730)"
                self.expectedToLeak = True
            if "Did not receive all required callbacks" in msg:
                print "Ignoring memory leaks (bug 973384)"
                self.expectedToLeak = True
            if "Ran out of memory while building cycle collector graph" in msg or "AddPurpleRoot failed" in msg:
                print "Ignoring memory leaks (CC OOM)"
                self.expectedToLeak = True
            if self.nsassertionCount == 100:
                print "domInteresting.py: not considering it a failure if browser hangs, because assertions are slow with stack-printing on. Please test in opt builds too, or fix the assertion bugs."
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
            not ("Tear-off objects remain in hashtable at shutdown" in msg and self.expectedToLeak) and
            not ("Assertion failed: _cairo_status_is_error" in msg and isWin) and # A frequent error that I cannot reproduce
            not ("JS_IsExceptionPending" in msg) and # Bug 813646, bug 735082, bug 735081
            not (self.goingDownHard and isWin) and # Bug 763182
            True)

        if newAssertion:
            self.newAssertionFailure = True
            self.printAndLog("@@@ " + msg)
        if assertionSeverity == detect_assertions.FATAL_ASSERT:
            self.sawFatalAssertion = True
            self.goingDownHard = True
            if not overlyGenericAssertion:
                self.crashIsKnown = True

        if not self.mallocFailure and detect_malloc_errors.scanLine(msgLF) and not "bug 931331":
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
            self.goingDownHard = True
            self.crashIsKnown = True

        if msg.startswith("PROCESS-CRASH | automation.py | application crashed"):
            print "We have a crash on our hands!"
            self.crashProcessor = "minidump_stackwalk"
            self.crashSignature = msg[len("PROCESS-CRASH | automation.py | application crashed") : ]

        if "ERROR: AddressSanitizer" in msg:
            print "We have an asan crash on our hands!"
            self.crashProcessor = "asan"
            m = re.search("on unknown address (0x\S+)", msg)
            if m and int(m.group(1), 16) < 0x10000:
                # A null dereference. Ignore the crash if it was preceded by malloc returning null due to OOM.
                # It would be good to know if it were a read, write, or execute.  But ASan doesn't have that info for SEGVs, I guess?
                if self.outOfMemory:
                    self.printAndLog("%%% We ran out of memory, then dereferenced null.")
                    self.crashIsKnown = True
                else:
                    self.printAndLog("%%% This looks like a null deref bug.")
            else:
                # Not a null dereference.
                self.printAndLog("%%% Assuming this ASan crash is exploitable")
                self.crashIsExploitable = True

        if "WARNING: AddressSanitizer failed to allocate" in msg:
            self.outOfMemory = True

        if msg.startswith("freed by thread") or msg.startswith("previously allocated by thread"):
            # We don't want to treat these as part of the stack trace for the purpose of detect_interesting_crashes.
            self.crashBoringBits = True

        if self.crashProcessor and len(self.summaryLog) < 300:
            self.summaryLog.append(msgLF)
        if self.crashProcessor and not self.crashBoringBits and detect_interesting_crashes.isKnownCrashSignature(msg, self.crashIsExploitable):
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
            if self.crashMightBeTooMuchRecursion and msg.startswith(" 3 ") and not self.crashIsKnown:
                self.printAndLog("%%% The stack trace is not broken, so it's more likely to be a stack buffer overflow.")
                self.crashMightBeTooMuchRecursion = False
            if self.crashMightBeTooMuchRecursion and msg.startswith("Thread 1"):
                self.printAndLog("%%% The stack trace is broken, so it's more likely to be a too-much-recursion crash.")
                self.crashIsKnown = True
            if msg.endswith(".dmp has no thread list"):
                self.printAndLog("%%% This crash report is totally busted. Giving up.")
                self.crashIsKnown = True

        if "goQuitApplication" in msg:
            self.expectChromeFailure = True
        if (not self.expectChromeFailure and jsInChrome(msg) and jsFailure(msg) and not knownChromeFailure(msg)):
            self.printAndLog("@@@ " + msg)
            self.sawChromeFailure = True

        return msgLF

    def printAndLog(self, msg):
        print "$ " + msg
        self.fullLogHead.append(msg + "\n")
        self.summaryLog.append(msg + "\n")

def jsFailure(msg):
    return ("uncaught exception" in msg or
            "JavaScript error" in msg or
            "JavaScript Error" in msg or
            "[Exception..." in msg or
            "JS Component Loader: ERROR" in msg or
            "ReferenceError" in msg or
            "TypeError" in msg or
            "Full stack:" in msg or
            "System JS : ERROR" in msg or
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
            "System JS : ERROR" in msg or
            False)

def knownChromeFailure(msg):
    return (
        ("nsIWebProgress.DOMWindow" in msg or "nsIWebProgress.isTopLevel" in msg) or # bug 732593
        "installStatus is null" in msg or # bug 693237
        "aTab is null" in msg or # bug 693239
        "browser is null" in msg or # bug 693239?
        "nsIWebContentHandlerRegistrar::registerProtocolHandler" in msg or # bug 732692, bug 693270
        "nsIWebContentHandlerRegistrar::registerContentHandler" in msg or # bug 732692, bug 693270
        "prompt aborted by user" in msg or # thrown intentionally in nsPrompter.js
        "nsIIOService.getProtocolHandler" in msg or # bug 746878
        "tipElement is null" in msg or # bug 746893
        ("browser.xul" in msg and "gBrowserInit is not defined" in msg) or # Bug 897867
        ("browser.js" in msg and "overlayText is null" in msg) or # Bug 797945
        ("browser.js" in msg and "organizer.PlacesOrganizer" in msg) or # Bug 801436?
        ("browser.js" in msg and "element is null" in msg) or # trustedKeyEvent can artifically direct F6 at browser.js (focusNextFrame) when the focused window is a Scratchpad window
        ("browser.js" in msg and "this.UIModule is undefined" in msg) or  # Bug 877013
        ("browser.js" in msg and "this._cps2 is undefined" in msg) or     # Bug 877013
        ("browser.js" in msg and "this.button is null" in msg) or         # Bug 877013
        ("browser.js" in msg and "aBrowser is null" in msg) or            # Bug 957922
        ("browser.xml" in msg and "this.docShell is null" in msg) or      # Bug 919362
        ("places.js" in msg and "PlacesUIUtils is not defined" in msg) or # Bug 801436
        ("places.js" in msg and "this._places is null" in msg) or         # Bug 893322
        ("pageInfo.js" in msg and "elem.ownerDocument.defaultView" in msg) or # Bug 799329
        ("pageInfo.js" in msg and "can't access dead object" in msg) or # Bug 799329 ?
        ("pageInfo.js" in msg and "imgIRequest.image" in msg) or # Bug 801930
        ("pageInfo.js" in msg and "NS_ERROR_MALFORMED_URI" in msg) or # Bug 949927
        ("aboutHome.js" in msg and "The operation is insecure" in msg) or # Bug 873300
        ("SessionStore.jsm" in msg and "browser.contentDocument.body is null" in msg) or # Bug 883014
        ("PermissionSettings.js" in msg and "aWindow.document is null" in msg) or # Bug 927294
        ("nsDOMIdentity.js" in msg and "aWindow.document is null" in msg) or # Bug 931286
        ("tabbrowser.xml" in msg and "b.webProgress is undefined" in msg) or # Bug 927339
        ("urlbarBindings.xml" in msg and "aUrl is undefined" in msg) or # Bug 931622
        ("ConsoleAPI.js" in msg and "can't access dead object" in msg) or # Bug 931304
        ("search.xml" in msg and "this.updateDisplay is not a function" in msg) or # Bug 903274
        ("webrtcUI.jsm" in msg and "nsIDOMGetUserMediaErrorCallback" in msg) or # Bug 947404
        ("webrtcUI.jsm" in msg and "can't access dead object" in msg) or # Bug 949907, but also check whether webrtc-js-dom still hits it
        ("webrtcUI.jsm" in msg and "NS_ERROR_OUT_OF_MEMORY" in msg) or # Seems legit (webrtc-js-oom)
        ("webrtcUI.jsm" in msg and ".WebrtcIndicator is undefined" in msg) or # Bug 949920
        ("webrtcUI.jsm" in msg and "getBrowserForWindow" in msg) or # Bug 950327
        ("webrtcUI.jsm" in msg) or # Bug 973318
        ("FeedConverter.js" in msg and "NS_ERROR_MALFORMED_URI" in msg) or # Bug 949926
        "DOMIdentity.jsm" in msg or # Bug 973397, bug 973398
        "abouthealth.js" in msg or # Bug 895113
        "WindowsPrefSync.jsm" in msg or # Bug 947581
        "nsIFeedWriter::close" in msg or # Bug 813408
        "SidebarUtils is not defined" in msg or # Bug 856250
        "this.keyManager_ is null" in msg or # mostly happens when i manually quit during a fuzz run
        "pbu_privacyContextFromWindow" in msg or # bug 931304 whenfixed 'pb'

        # opening dev tools while simultaneously opening and closing tabs is mean
        ("devtools/framework/toolbox.js" in msg and "container is null: TBOX_destroy" in msg) or
        ("browser.js" in msg and "gURLBar.editor is undefined" in msg) or
        ("browser.js" in msg and "browser is undefined" in msg) or
        ("browser.js" in msg and "gNavigatorBundle.getString is not a function" in msg) or
        ("browser.js" in msg and "gBrowser.browsers is undefined" in msg) or
        "devtools" in msg or # most devtools js errors I hit are uninteresting races

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
            print "browserDir: " + repr(browserDir)
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
            #print "Looking for prefsFile: " + prefsFile
            if os.path.exists(prefsFile):
                #print "Found prefs.txt"
                with open(prefsFile) as f:
                    return f.read()
    return ""

def removeIfExists(filename):
    if os.path.exists(filename):
        os.remove(filename)

def rdfInit(args):
    """
    Returns (levelAndLines, options).

    levelAndLines is a function that runs Firefox in a clean profile and analyzes Firefox's output for bugs.
    """

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

    runBrowserOptions = []
    if dirs.symbolsDir:
        runBrowserOptions.append("--symbols-dir=" + dirs.symbolsDir)

    env = os.environ.copy()
    env['MOZ_FUZZING_SAFE'] = '1'
    env['REFTEST_FILES_DIR'] = dirs.reftestFilesDir
    env['ASAN_SYMBOLIZER_PATH'] = os.path.expanduser("~/llvm/build/Release/bin/llvm-symbolizer")
    if dirs.stackwalk:
        env['MINIDUMP_STACKWALK'] = dirs.stackwalk
    runbrowserpy = [sys.executable, "-u", os.path.join(THIS_SCRIPT_DIRECTORY, "runbrowser.py")]

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
    #      "--show-possibly-lost=no" + " " +
          "--smc-check=all-non-file" + " " +
    #      "--track-origins=yes" + " " +
    #      "--num-callers=50" + " " +
          "--quiet"
        )

    def levelAndLines(url, logPrefix=None, extraPrefs="", quiet=False, leaveProfile=False):
        """Run Firefox using the profile created above, detecting bugs and stuff."""

        profileDir = mkdtemp(prefix="domfuzz-rdf-profile")
        createDOMFuzzProfile(profileDir)
        writePrefs(profileDir, extraPrefs)

        runBrowserArgs = [dirs.reftestScriptDir, dirs.utilityDir, profileDir]

        assert logPrefix # :(
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
                if not quiet:
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
                alh.printAndLog("%%% Known crash (from " + alh.crashProcessor + ")" + alh.crashSignature)
            else:
                alh.printAndLog("@@@ New crash (from " + alh.crashProcessor + ")" + alh.crashSignature)
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
            if signum != signal.SIGKILL and signum != signal.SIGTERM and not alh.crashProcessor:
                # Well, maybe we have a core file or log from the Mac crash reporter.
                wantStack = True
                crashlog = grabCrashLog(os.path.basename(alh.theapp), alh.theapp, alh.pid, logPrefix, wantStack)
                if crashlog:
                    with open(crashlog) as f:
                        crashText = f.read()
                    if not quiet:
                        print "== " + crashlog + " =="
                        print crashText
                        print "== " + crashlog + " =="
                    if "Reading symbols for shared libraries" in crashText:
                        crashProcessor = "gdb"
                        expectAfterFunctionName = " ("
                    else:
                        crashProcessor = "mac crash reporter"
                        expectAfterFunctionName = " + "
                    processedCorrectly = False
                    for j in ["main", "XRE_main", "exit"]:
                        if (" " + j + expectAfterFunctionName) in crashText:
                            processedCorrectly = True
                            break
                    if not processedCorrectly:
                        # Lack of 'main' could mean:
                        #   * This build only has breakpad symbols, not native symbols
                        #   * This was a too-much-recursion crash
                        # This code does not handle too-much-recursion crashes well.
                        # But it only matters for the rare case of too-much-recursion crashes on Mac/Linux without breakpad.
                        alh.printAndLog("%%% Busted or too-much-recursion crash report (from " + crashProcessor + ")")
                    elif alh.crashIsKnown:
                        alh.printAndLog("%%% Ignoring crash report (from " + crashProcessor + ")")
                    elif detect_interesting_crashes.amiss(knownPath, crashlog, True):
                        alh.printAndLog("@@@ New crash (from " + crashProcessor + ")")
                        lev = max(lev, DOM_NEW_ASSERT_OR_CRASH)
                    else:
                        alh.printAndLog("%%% Known crash (from " + crashProcessor + ")")
        elif status == 1:
            alh.printAndLog("%%% Exited with status 1 (OOM or plugin crash?)")
        elif status == -2147483645 and isWin:
            alh.printAndLog("%%% Exited with status -2147483645 (plugin issue, bug 867263?)")
        elif status != 0 and not (isWin and alh.sawFatalAssertion):
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

        print("DOMFUZZ INFO | domInteresting.py | " + str(lev))
        return (lev, alh.FRClines)

    return levelAndLines, options # return a closure along with the set of options

# For use by Lithium
def init(args):
    global levelAndLinesForLithium, deleteProfileForLithium, minimumInterestingLevel, lithiumURL, extraPrefsForLithium
    levelAndLinesForLithium, options = rdfInit(args)
    minimumInterestingLevel = options.minimumInterestingLevel
    lithiumURL = options.argURL
def interesting(args, tempPrefix):
    extraPrefs = grabExtraPrefs(lithiumURL) # Here in case Lithium is reducing the prefs file
    actualLevel, lines = levelAndLinesForLithium(lithiumURL, logPrefix = tempPrefix, extraPrefs = extraPrefs)
    return actualLevel >= minimumInterestingLevel

# For direct (usually manual) invocations
def directMain():
    logPrefix = os.path.join(mkdtemp(prefix="domfuzz-rdf-main"), "t")
    print logPrefix
    levelAndLines, options = rdfInit(sys.argv[1:])
    if options.argURL:
        extraPrefs = grabExtraPrefs(options.argURL)
    else:
        extraPrefs = ""
    level, lines = levelAndLines(options.argURL or "https://bugzilla.mozilla.org/", logPrefix, extraPrefs=extraPrefs, leaveProfile=True)
    print level
    sys.exit(level)

if __name__ == "__main__":
    directMain()

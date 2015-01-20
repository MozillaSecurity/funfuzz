import os
import sys
import re

import detect_interesting_crashes

THIS_SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

path2 = os.path.abspath(os.path.join(THIS_SCRIPT_DIRECTORY, os.pardir, 'util'))
sys.path.append(path2)
import subprocesses as sps

class CrashWatcher:

    '''
    Call processOutputLine on each line of stderr, then
    call readCrashLog if you have an external crash log file (e.g. from sps.grabCrashLog)
    '''

    def __init__(self, knownPath, ignoreASanOOM, noteCallback):
        self.crashProcessor = None
        self.crashBoringBits = False
        self.crashMightBeTooMuchRecursion = False
        self.crashIsKnown = False
        self.crashIsExploitable = False
        self.crashSignature = ""
        self.noteCallback = noteCallback
        self.outOfMemory = False
        self.knownPath = knownPath
        self.ignoreASanOOM = ignoreASanOOM

        if not detect_interesting_crashes.ready:
            detect_interesting_crashes.readIgnoreLists(knownPath)

        detect_interesting_crashes.resetCounts()

    def processOutputLine(self, msg):
        '''Detect signs of crashes from stderr (breakpad, asan)'''

        if msg.startswith("PROCESS-CRASH | automation.py | application crashed"):
            #self.noteCallback("We have a crash on our hands!")
            self.crashProcessor = "minidump_stackwalk"
            self.crashSignature = msg[len("PROCESS-CRASH | automation.py | application crashed") : ]

        if "WARNING: AddressSanitizer failed to allocate" in msg:
            # ASan will return null and the program may continue (?)
            # We will ignore subsequent null derefs if ignoreASanOOM is true.
            self.outOfMemory = True

        if "ERROR: AddressSanitizer failed to allocate" in msg or "AddressSanitizer's allocator is terminating the process instead of returning 0" in msg:
            # ASan will immediately abort the program.
            # As of LLVM r190127, this looks like:
            #     WARNING: AddressSanitizer failed to allocate 0x0fffffffffff bytes
            #     AddressSanitizer's allocator is terminating the process instead of returning 0
            #     If you don't like this behavior set allocator_may_return_null=1
            # If you're interested in OOM crashes, you can set ASAN_OPTIONS=allocator_may_return_null=1
            self.crashProcessor = "asan"
            self.crashIsKnown = True

        if "ERROR: AddressSanitizer" in msg:
            #self.noteCallback("We have an asan crash on our hands!")
            self.crashProcessor = "asan"
            m = re.search("on unknown address 0x(\S+)", msg)
            if m and int(m.group(1), 16) < 0x10000:
                # A null dereference. Ignore the crash if it was preceded by malloc returning null due to OOM.
                # It would be good to know if it were a read, write, or execute.  But ASan doesn't have that info for SEGVs, I guess?
                if self.outOfMemory:
                    #self.noteCallback("We ran out of memory, then dereferenced null.")
                    if self.ignoreASanOOM:
                        self.crashIsKnown = True
                else:
                    #self.noteCallback("This looks like a null deref bug.")
                    pass
            elif sps.isMac and "stack-overflow on address 0x7fff" in msg:
                # self.noteCallback("This ASan crash may be a too-much-recursion bug")
                pass
            else:
                # A memory error that is NOT on one of our well-known guard pages (null, stack limit)!
                # self.noteCallback("Assuming this ASan crash is exploitable")
                self.crashIsExploitable = True

        if msg.startswith("freed by thread") or msg.startswith("previously allocated by thread"):
            # We don't want to treat these as part of the stack trace for the purpose of detect_interesting_crashes.
            self.crashBoringBits = True

        if self.crashProcessor and not self.crashBoringBits and detect_interesting_crashes.isKnownCrashSignature(msg, self.crashIsExploitable):
            self.noteCallback("Known crash signature: " + msg)
            self.crashIsKnown = True

        if sps.isMac:
            # There are several [TMR] bugs listed in crashes.txt
            # Bug 507876 is a breakpad issue that means too-much-recursion crashes don't give me stack traces on Mac
            # (and Linux, but differently).
            # The combination means we lose.
            if (msg.startswith("Crash address: 0xffffffffbf7ff") or msg.startswith("Crash address: 0x5f3fff")):
                #self.noteCallback("This crash is at the Mac stack guard page. It is probably a too-much-recursion crash or a stack buffer overflow.")
                self.crashMightBeTooMuchRecursion = True
            if self.crashMightBeTooMuchRecursion and msg.startswith(" 3 ") and not self.crashIsKnown:
                #self.noteCallback("The stack trace is not broken, so it's more likely to be a stack buffer overflow.")
                self.crashMightBeTooMuchRecursion = False
            if self.crashMightBeTooMuchRecursion and msg.startswith("Thread 1"):
                #self.noteCallback("The stack trace is broken, so it's more likely to be a too-much-recursion crash.")
                self.crashIsKnown = True
            if msg.endswith(".dmp has no thread list"):
                #self.noteCallback("This crash report is totally busted. Giving up.")
                self.crashIsKnown = True

    def readCrashLog(self, crashlog):
        if not os.path.isfile(crashlog):
            if self.crashProcessor != "asan":
                self.noteCallback("Crash log is missing!")
            return

        with open(crashlog) as f:
            crashText = f.read()

        if "Reading symbols for shared libraries" in crashText or "Core was generated by" in crashText:
            self.crashProcessor = "gdb"
            expectAfterFunctionName = " ("
        elif "Microsoft (R) Windows Debugger" in crashText:
            self.crashProcessor = "cdb"
        else:
            self.crashProcessor = "mac crash reporter"
            expectAfterFunctionName = " + "

        if False: # self.crashProcessor != "cdb" and not crashWasProcessedCorrectly(crashText, expectAfterFunctionName):
            # TODO: if dom fuzzer keeps hitting this kind of problem, look for a more specific way to ignore these bogus crashes
            # that does not also ignore anything that just fails to, for example, trace the stack up through JIT code.
            # (See email thread between Jesse and Gary titled "Mac crashes not being detected as interesting")
            #self.noteCallback("Busted or too-much-recursion crash report (from " + self.crashProcessor + ")")
            self.crashIsKnown = True
        elif self.crashIsKnown:
            #self.noteCallback("Ignoring crash report (from " + self.crashProcessor + ")")
            pass
        elif not detect_interesting_crashes.amiss(self.knownPath, crashlog, True):
            self.crashIsKnown = True

def crashWasProcessedCorrectly(crashText, expectAfterFunctionName):
    # Lack of 'main' could mean:
    #   * This build only has breakpad symbols, not native symbols
    #   * This was a too-much-recursion crash
    # This code does not handle too-much-recursion crashes well.
    # But it only matters for the rare case of too-much-recursion crashes on Mac/Linux without breakpad.
    for j in ["main", "XRE_main", "exit"]:
        if (" " + j + expectAfterFunctionName) in crashText:
            # We have enough symbols from Firefox
            return True
    return False

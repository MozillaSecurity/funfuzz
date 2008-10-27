#!/usr/bin/env python


def ath(array):
    hash = {}
    for s in array:
        hash[s] = True
    return hash


knownHash = ath([

# bug 391976
"nsMathMLContainerFrame",
"nsMathMLmtableOuterFrame",
"nsMathMLmtdInnerFrame",
"nsMathMLmactionFrame",

# Bug 398462
"nsBaseAppShell",
"nsRunnable",

# Bug 403199
"nsSimpleNestedURI"

])

# Things that are known to leak AND entrain smaller objects.
# If one of these leaks, leaks of small objects will not be reported.
knownLargeHash = ath([

# Bug 397206
"BackstagePass",

# Bug 102229 or bug 419562
"nsDNSService",

# Bug 424418
"nsRDFResource",

# Bug 417630 and friends
"nsJVMManager"
])

# Large items that
# - should be reported even if things in knownLargeHash leak
# - should quell the reporting of smaller objects
# currently empty :(
otherLargeHash = ath([
"nsGlobalWindow",
"nsDocument",
"nsDocShell" 
])


def amiss(logPrefix):
    currentFile = file(logPrefix + "-out", "r")
    
    for line in currentFile:
        # line = line.strip("\x07").rstrip("\n")
        if (line.startswith("nsTraceRefcntImpl::DumpStatistics")):
            break
    else:
        currentFile.close()
        return False
        
    smallLeaks = ""
    largeKnownLeaks = ""
    largeOtherLeaks = ""

    for line in currentFile:
        line = line.strip("\x07").rstrip("\n").lstrip(" ")
        if (line == "nsStringStats"):
            break
        a = line.split(" ")[1]
        if a in knownLargeHash:
            largeKnownLeaks += "*** Large K object " + a + "\n"
        if a in otherLargeHash:
            largeOtherLeaks += "*** Large O object " + a + "\n"
        if not a in knownHash:
            smallLeaks += a + "\n"

    if largeOtherLeaks != "":
        print "Leaked:"
        print largeOtherLeaks
        print largeKnownLeaks
        currentFile.close()
        return True
    elif largeKnownLeaks != "":
        # print "(Known large leaks, and no other large leaks, so all leaks were ignored)"
        currentFile.close()
        return False
    elif smallLeaks != "":
        print "Leaked:"
        print smallLeaks
        currentFile.close()
        return True
    else:
        # print "No leaks :)"
        currentFile.close()
        return False

# print "detect_leaks is ready"

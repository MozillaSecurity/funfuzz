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
"nsSimpleNestedURI",

# Bug 467693
"nsStringBuffer"

])

# Things that are known to leak AND entrain smaller objects.
# If one of these leaks, leaks of small objects will not be reported.
knownLargeHash = ath([

# Bug 467686
"nsGlobalWindow",
"nsGenericElement",

# Bug 397206
"BackstagePass",

# Bug 102229 or bug 419562
"nsDNSService",

# Bug 463724
"nsHTMLDNSPrefetch::nsDeferrals",
"nsDNSPrefetch",
"nsDNSAsyncRequest",
"nsHostResolver",

# Bug 424418
"nsRDFResource",

# Bug 417630 and friends
"nsJVMManager"

])

# Large items that
# - should be reported even if things in knownLargeHash leak
# - should quell the reporting of smaller objects
otherLargeHash = ath([
])


def amiss(logPrefix):
    currentFile = file(logPrefix + "-out", "r")
    sawLeakStats = False
    
    for line in currentFile:
        line = line.rstrip("\n")
        if (line == "== BloatView: ALL (cumulative) LEAK STATISTICS"):
            sawLeakStats = True
        # This line appears only if there are leaks
        if (line.endswith("Mean       StdDev")):
            break
    else:
        if sawLeakStats:
            #print "No leaks :)"
            pass
        else:
            print "Didn't see leak stats"
        currentFile.close()
        return False

    smallLeaks = ""
    largeKnownLeaks = ""
    largeOtherLeaks = ""

    for line in currentFile:
        line = line.strip("\x07").rstrip("\n").lstrip(" ")
        if (line == ""):
            break
        a = line.split(" ")[1]
        if a == "TOTAL":
            continue
        # print "Leaked at least one: " + a
        if a in knownLargeHash:
            largeKnownLeaks += "*** Leaked large object " + a + " (known)\n"
        if a in otherLargeHash:
            largeOtherLeaks += "*** Leaked large object " + a + "\n"
        if not a in knownHash:
            smallLeaks += a + "\n"

    if largeOtherLeaks != "":
        print "Leaked large objects:"
        print largeOtherLeaks
        # print "Also leaked 'known' large objects:"
        # print largeKnownLeaks
        currentFile.close()
        return True
    elif largeKnownLeaks != "":
        # print "(Known large leaks, and no other large leaks, so all leaks were ignored)"
        # print largeKnownLeaks
        currentFile.close()
        return False
    elif smallLeaks != "":
        print "Leaked:"
        print smallLeaks
        currentFile.close()
        return True
    else:
        # print "(Only known small leaks)"
        currentFile.close()
        return False

# print "detect_leaks is ready"

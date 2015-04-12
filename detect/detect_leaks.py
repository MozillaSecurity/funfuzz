#!/usr/bin/env python

import os
import sys
import findIgnoreLists

ready = False
knownObjects = dict()
sizes = 0

def readKnownLeakList(knownPath):
    global ready, knownObjects, sizes

    knownLeaksFn = os.path.join(findIgnoreLists.THIS_REPO_PATH, "known", knownPath, "rleak.txt")
    with open(knownLeaksFn) as f:
        for line in f:
            line = line.split("#")[0]
            line = line.strip()
            parts = line.split(" ")
            if parts[0] == "":
                continue
            elif parts[0] == "SIZE":
                sizes += 1
            elif parts[0] == "LEAK" and len(parts) == 2:
                objname = parts[1]
                knownObjects[objname] = {'size': 10-sizes, 'knownToLeak': True}
            elif len(parts) == 1:
                objname = parts[0]
                knownObjects[objname] = {'size': 10-sizes, 'knownToLeak': False}
            else:
                raise Exception("What? " + repr(parts))

    #print "detect_leaks is ready"
    #print repr(knownObjects)

    ready = True


def amiss(knownPath, leakLogFn, verbose=False):
    if not ready:
        readKnownLeakList(knownPath)
    sawLeakStats = False

    with open(leakLogFn) as leakLog:

        for line in leakLog:
            line = line.rstrip()
            if line.startswith("nsTraceRefcntImpl::DumpStatistics"):
                continue
            if (line.startswith("== BloatView: ALL (cumulative) LEAK STATISTICS")):
                sawLeakStats = True
            # This line appears only if there are leaks with XPCOM_MEM_LEAK_LOG (but always shows with XPCOM_MEM_BLOAT_LOG, oops)
            if (line.endswith("Total      Rem")):
                break
        else:
            if verbose:
                if sawLeakStats:
                    print "detect_leaks: PASS with no leaks at all :)"
                else:
                    print "detect_leaks: PASS missing leak stats, don't care enough to fail"
            return False

        largestA = -1 # largest object known to leak
        largestB = -2 # largest object not known to leak

        for line in leakLog:
            line = line.strip("\x07").rstrip("\n").lstrip(" ")
            if (line == ""):
                break
            if line.startswith("nsTraceRefcntImpl::DumpStatistics"):
                continue
            objname = line.split(" ")[1]
            if objname == "TOTAL":
                continue
            info = knownObjects.get(objname, {'size': 10-sizes, 'knownToLeak': False})
            if verbose:
                print "detect_leaks: Leaked " + repr(info) + " " + repr(objname)
            if info.get("knownToLeak"):
                largestA = max(largestA, info.get("size"))
            else:
                largestB = max(largestB, info.get("size"))

    if largestB >= largestA:
        if verbose:
            print "detect_leaks: FAIL " + str(largestB) + " " + str(largestA)
        return True
    else:
        if verbose:
            print "detect_leaks: PASS " + str(largestB) + " " + str(largestA)
        return False

# For standalone use
if __name__ == "__main__":
    knownPath = sys.argv[1]
    leakLogFn = sys.argv[2]
    print amiss(knownPath, leakLogFn, verbose=True)

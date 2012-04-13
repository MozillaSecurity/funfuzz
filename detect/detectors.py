#!/usr/bin/env python


from __future__ import with_statement
import os, sys, platform, signal

class Detector:
  def __init__():
    pass

  def readIgnoreLists(self, knownPath, filename, readerFunction):
      while os.path.basename(knownPath) != "known":
          filename = os.path.join(knownPath, filename)
          if os.path.exists(filename):
               readerFunction(filename)
          knownPath = os.path.dirname(os.path.dirname(filename))

# Recognizes NS_ASSERTIONs based on condition, text, and filename (ignoring irrelevant parts of the path)
# Recognizes JS_ASSERT based on condition only :(
# Recognizes ObjC exceptions based on message, since there is no stack information available, at least on Tiger.
class AssertionDetector(Detector):
  def __init__(knownPath):
    self.simpleAssertionsIgnoreList = []
    self.twoPartAssertionsIgnoreList = []
    self.readIgnoreLists(knownPath, "assertions.txt", self.readAssertionsIgnoreList)
    print "detect_assertions is ready (ignoring %d strings without filenames and %d strings with filenames)" % (len(self.simpleIgnoreList), len(self.twoPartIgnoreList))

  def readAssertionsIgnoreList(self, filename):
      with open(filename) as ignoreFile:
          for line in ignoreFile:
              line = line.rstrip()
              if ((len(line) > 0) and not line.startswith("#")):
                  mpi = line.find(", file ")  # NS_ASSERTION and friends use this format
                  if (mpi == -1):
                      mpi = line.find(": file ")  # NS_ABORT uses this format
                  if (mpi == -1):
                      self.simpleIgnoreList.append(line)
                  else:
                      self.twoPartIgnoreList.append((line[:mpi+7], line[mpi+7:]))

  # Called directly by domInteresting.py
  def scanLineAssertions(self, line):
      line = line.strip("\x07").rstrip("\n")

      if self.hasAssertion(line) and not self.ignoreAssertion(line):
          return True

      return False

  def scanFileAssertions(self, currentFile, verbose, ignoreKnownAssertions):
      foundSomething = False

      # map from (assertion message) to (true, if seen in the current file)
      seenInCurrentFile = {}

      for line in currentFile:
          line = line.strip("\x07").rstrip("\n")
          if (self.hasAssertion(line) and not (line in seenInCurrentFile)):
              seenInCurrentFile[line] = True
              if not (self.ignore(line)):
                  print "! New assertion: "
                  print line
                  foundSomething = True
              elif not ignoreKnownAssertions:
                  foundSomething = True
              elif verbose:
                  print "@ Known assertion: "
                  print line

      currentFile.close()

      return foundSomething

  def hasAssertion(self, line):
      return (line.startswith("###!!!") or # NS_ASSERTION and also aborts
              line.startswith("Assertion failure:") or # spidermonkey; nss
              line.find("Assertion failed:") != -1 or # assert.h e.g. as used by harfbuzz
              line.find("Mozilla has caught an Obj-C exception") != -1
             )

  def ignoreAssertion(self, assertion):
      for ig in self.simpleIgnoreList:
          if assertion.find(ig) != -1:
              return True
      for (part1, part2) in self.twoPartIgnoreList:
          if assertion.find(part1) != -1 and assertion.replace('\\', '/').find(part2) != -1:
              return True
      return False


  # For use by af_timed_run and jsunhappy.py
  def amiss(self, logPrefix, verbose, ignoreKnownAssertions=True):
      with open(logPrefix + "-err") as currentFile:
          return self.scanFile(currentFile, verbose, ignoreKnownAssertions)

class CrashDetector(Detector):
  def __init__(self, knownPath):
    self.ignoreList = []
    self.TOO_MUCH_RECURSION_MAGIC = "[TMR] "
    self.readIgnoreLists(knownPath, "crashes.txt", self.readCrashesIgnoreList)
    print "detect_interesting_crashes is ready (ignoring %d strings)" % (len(self.ignoreList))

  def readCrashesIgnoreList(self, filename):
      with open(filename) as ignoreFile:
          for line in ignoreFile:
              line = line.rstrip()
              if line.startswith(self.TOO_MUCH_RECURSION_MAGIC):
                  self.ignoreList.append({"seenCount": 0, "needCount": 9, "theString": line[len(self.TOO_MUCH_RECURSION_MAGIC):]})
              elif len(line) > 0 and not line.startswith("#"):
                  self.ignoreList.append({"seenCount": 0, "needCount": 1, "theString": line})


  def amiss(self, crashLogFilename, verbose, msg):
      resetCounts()
      igmatch = []

      if os.path.exists(crashLogFilename):
          with open(crashLogFilename, "r") as f:
              for line in f:
                  if self.isKnownCrashSignature(line):
                      igmatch.append(line.rstrip())

          if len(igmatch) == 0:
              # Would be great to print [@ nsFoo::Bar] in addition to the filename, but
              # that would require understanding the crash log format much better than
              # this script currently does.
              print "Unknown crash: " + crashLogFilename
              return True
          else:
              if verbose:
                  print "@ Known crash: " + ", ".join(igmatch)
              return False
      else:
          if platform.mac_ver()[0].startswith("10.4") and msg.find("SIGABRT") != -1:
              # Tiger doesn't create crash logs for aborts.  No cause for alarm.
              return False
          else:
              print "Unknown crash (crash log is missing)"
              return True

  def isKnownCrashSignature(self, line):
      for ig in self.ignoreList:
          if line.find(ig["theString"]) != -1:
              ig["seenCount"] += 1
              if ig["seenCount"] >= ig["needCount"]:
                  return True
      return False

  def resetCounts(self):
      for ig in self.ignoreList:
          ig["seenCount"] = 0


class LeakDetector(Detector):
  def __init__(self, knownPath):
    self.knownObjects = dict()
    self.sizes = 0
    self.readIgnoreLists(knownPath, "rleak.txt", self.readLeaksIgnoreList)
    #print "detect_leaks is ready"
    #print repr(self.knownObjects)

  def readLeaksIgnoreList(self, filename):
      with open(filename) as ignoreFile:
          for line in ignoreFile:
            line = line.split("#")[0]
            line = line.strip()
            parts = line.split(" ")
            if parts[0] == "":
                continue
            elif parts[0] == "SIZE":
                self.sizes += 1
            elif parts[0] == "LEAK" and len(parts) == 2:
                objname = parts[1]
                self.knownObjects[objname] = {'size': 10-self.sizes, 'knownToLeak': True}
            elif len(parts) == 1:
                objname = parts[0]
                self.knownObjects[objname] = {'size': 10-self.sizes, 'knownToLeak': False}
            else:
                raise Exception("What? " + repr(parts))

  def amiss(self, leakLogFn, verbose=False):
      sawLeakStats = False

      with open(leakLogFn) as leakLog:

          for line in leakLog:
              line = line.rstrip()
              if line.startswith("nsTraceRefcntImpl::DumpStatistics"):
                  continue
              if (line.startswith("== BloatView: ALL (cumulative) LEAK STATISTICS")):
                  sawLeakStats = True
              # This line appears only if there are leaks with XPCOM_MEM_LEAK_LOG (but always shows with XPCOM_MEM_BLOAT_LOG, oops)
              if (line.endswith("Mean       StdDev")):
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
              info = self.knownObjects.get(objname, {'size': 10-self.sizes, 'knownToLeak': False})
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


class MallocErrorDetector(Detector):
  def __init__(self, knownPath):
    self.pline = ""
    self.ppline = ""

  def amiss(logPrefix):
      foundSomething = False

      self.pline = ""
      self.ppline = ""

      with open(logPrefix + "-err") as f:
          for line in f:
              if scanLine(line):
                  foundSomething = True
                  break # Don't flood the log with repeated malloc failures

      return foundSomething


  def scanLine(line):
      line = line.strip("\x07").rstrip("\n")

      if (-1 != line.find("szone_error")
       or -1 != line.find("malloc_error_break")
       or -1 != line.find("MallocHelp")):
          if (-1 == self.pline.find("can't allocate region")):
              print ""
              print self.ppline
              print self.pline
              print line
              return True

      self.ppline = pline
      self.pline = line

# For standalone use
if __name__ == "__main__":
    knownPath = sys.argv[1]
    with open(sys.argv[2]) as currentFile:
        print scanFile(knownPath, currentFile, False, True)

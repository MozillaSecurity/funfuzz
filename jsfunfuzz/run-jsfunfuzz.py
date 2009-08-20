#!/usr/bin/env python
#
#/* ***** BEGIN LICENSE BLOCK	****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is jsfunfuzz.
#
# The Initial Developer of the Original Code is
# Gary Kwong.
# Portions created by the Initial Developer are Copyright (C) 2006-2008
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# * ***** END LICENSE BLOCK	****	/
#
# Version History:
#
# April 2008 - 1.x:
#   Initial idea, previously called ./jsfunfuzz-moz18branch-start-intelmac
# June 2008 - 2.x:
#   Rewritten from scratch to support the new hg fuzzing branch.
# August 2008 - 3.0.x:
#   Rewritten from scratch again to support command-line inputs and consolidate
#   all existing jsfunfuzz bash scripts.
# September 2008 - 3.1.x:
# 	Support fuzzing v8 engine.
# December 2008 - 3.2.x:
#   Supports 1.9.1.x branch. Rip out 1.8.1.x code.
# January 2009 - 3.3.x:
#   Rework v8 support, add JavaScriptCore support.
# July 2009 - 4.x:
#   Python rewrite - only 1.9.1.x, 1.9.2.x and TM planned for support. 1.9.0.x
#   is becoming obsolete in 5.5 months, mozTrunk is rarely fuzzed in favour of
#   TM, JavaScriptCore doesn't feel like a significant competing engine,
#   and Safari uses its own Nitro engine. v8 might come later too.
#
#
# Usage: python run-jsfunfuzz.py [dbg|opt] <supportedBranches>
#

import sys, os, subprocess, shutil, time


supportedBranches = "[191|192|tm]"
supportedBranchFOO = []
# Add supported branches here.
supportedBranchFOO.append('191')
supportedBranchFOO.append('192')
supportedBranchFOO.append('tm')
# FIXME supportedBranchFOO
# FIXME or use optparse (recommended, based on instinct feeling)

verbose = True  # Turn this to True to enable verbose output for debugging.
def verbose():
    print "\nDEBUG - Debug output follows..."
def exceptionBadOs():
    raise Exception("Unknown OS - Platform is unsupported.")
def exceptionBadCompileType():
    raise Exception("Unknown compileType - choose from [dbg|opt].")
def exceptionBadPosixBranchType():
    raise Exception("Not a supported POSIX branchType")
def exceptionBadNtBranchType():
    raise Exception("Not a supported NT branchType")

# The corresponding CLI requirements should be input, else output this error.
def error():
    print """
    
==========
| Error! |
==========
    
General usage: ./run-jsfunfuzz.py [dbg|opt] %s

    """ % supportedBranches


# Accept dbg and opt parameters for compileType only.
if (sys.argv[1] == "dbg") or (sys.argv[1] == "opt"):
    compileType = sys.argv[1]
else:
    error()
    print "Your compileType variable is \'" + compileType + "\'"
    raise Exception("Only \'dbg\' or \'opt\' are accepted as compileType.")


# Accept appropriate parameters for branchType.
if (sys.argv[2] == "191") or (sys.argv[2] == "192") or (sys.argv[2] == "tm"):
    branchType = sys.argv[2]
else:
    error()
    print "Your branchType variable is \'" + branchType + "\'"
    raise Exception("Please double-check your branchType from " + \
                    supportedBranches + ".")


# Definitions of the different repository and fuzzing locations.
if os.name == "posix":
    def locations():
        repoFuzzing = "~/fuzzing/"     # Location of the fuzzing repository.
        repo191 = "~/mozilla-1.9.1/"   # Location of the 1.9.1 repository.
        repo192 = "~/mozilla-1.9.2/"   # Location of the 1.9.2 repository.
        repoTM = "~/tracemonkey/"      # Location of the tracemonkey repository.
        fuzzPathStart = "~/Desktop/jsfunfuzz-" # Start of the fuzzing directory.
        return repoFuzzing, repo191, repo192, repoTM, fuzzPathStart
elif os.name == "nt":
    def locations():
        # ~ is not used because in XP, ~ contains spaces in
        # "Documents and Settings". This file assumes the repositories to be in
        # the root directory of the same drive as this file.
        repoFuzzing = "/fuzzing/"    # Location of the fuzzing repository.
        repo191 = "/mozilla-1.9.1/"  # Location of the 1.9.1 repository.
        repo192 = "/mozilla-1.9.2/"  # Location of the 1.9.2 repository.
        repoTM = "/tracemonkey/"     # Location of the tracemonkey repository.
        fuzzPathStart = "/jsfunfuzz-"   # Start of the fuzzing directory.
        return repoFuzzing, repo191, repo192, repoTM, fuzzPathStart
else:
    exceptionBadOs()
    
repoFuzzing, repo191, repo192, repoTM, fuzzPathStart = locations()

if verbose:
    verbose()
    print "DEBUG - repoFuzzing, repo191, repo192, repoTM, fuzzPathStart are:"
    print "DEBUG - %s\n" % ", ".join(locations())


# Expand the ~ folder on Linux/Mac.
fuzzPathRaw = fuzzPathStart + compileType + "-" + branchType + "/"
if os.name == "posix":
    fuzzPath = os.path.expanduser(fuzzPathRaw)
elif os.name == "nt":
    fuzzPath = fuzzPathRaw
else:
    exceptionBadOs()

# Create the fuzzing folder.
try:
    os.makedirs(fuzzPath)
except OSError:
    error()
    raise Exception("The fuzzing path at \'" + fuzzPath + "\' already exists!")

# Change to the fuzzing directory.
os.chdir(fuzzPath)


# Methods to copy the entire js source directory.
def posixCopyJsTree(repo):
    try:
        shutil.copytree(os.path.expanduser(repo + "js/src/"),"compilePath")
    except OSError:
        error()
        raise Exception("The js code repository directory located at '" + \
                        os.path.expanduser(repo + "js/src/") + \
                        "' doesn't exist!")
def ntCopyJsTree(repo):
    try:
        shutil.copytree(repo + "js/src/","compilePath")
    except OSError:
        error()
        raise Exception("The js code repository directory located at '" + \
                        repo + "js/src/' doesn't exist!")

# Copy the entire js tree to the fuzzPath.
if os.name == "posix":
    if branchType == "191":
        posixCopyJsTree(repo191)
    elif branchType == "192":
        posixCopyJsTree(repo192)
    elif branchType == "tm":
        posixCopyJsTree(repoTM)
    else:
        exceptionBadPosixBranchType()()
elif os.name == "nt":
    if branchType == "191":
        ntCopyJsTree(repo191)
    elif branchType == "192":
        ntCopyJsTree(repo192)
    elif branchType == "tm":
        ntCopyJsTree(repoTM)
    else:
        exceptionBadNtBranchType()()
else:
    exceptionBadOs()

# Change into compilation directory.
os.chdir("compilePath")


# Sniff platform and run different autoconf types:
if os.name == "posix":
    if os.uname()[0] == "Darwin":
        subprocess.call(["autoconf213"])
    elif os.uname()[0] == "Linux":
        subprocess.call(["autoconf2.13"])
elif os.name == "nt":
    subprocess.call(["local/bin/autoconf-2.13"], shell=True)
else:
    exceptionBadOs()


# Create objdirs within the compilePaths.
os.mkdir("dbg-objdir")
os.mkdir("opt-objdir")
os.chdir(compileType + "-objdir")


# Compile the first build.
if compileType == "dbg":
    subprocess.call(["../configure", "--disable-optimize", "--enable-debug"])
elif compileType == "opt":
    subprocess.call(["../configure", "--enable-optimize", "--disable-debug"])
else:
    exceptionBadCompileType()

def compileCopy(dbgOpt):
    # Run make using 2 cores.
    subprocess.call(["make", "-j2"])
    
    # Sniff platform and rename executable accordingly:
    if os.name == "posix":
        shellName = "js-" + dbgOpt + "-" + branchType + "-" + \
                    os.uname()[0].lower()
    elif os.name == "nt":
        shellName = "js-" + dbgOpt + "-" + branchType + "-" + os.name.lower()
    else:
        exceptionBadOs()
    
    # Copy js executable out into fuzzPath.
    shutil.copy2("js","../../" + shellName)
    
    return shellName

jsShellName = compileCopy(compileType)

# Change into compilePath directory for the opt build.
os.chdir("../")

if verbose:
    verbose()
    print "DEBUG - This should be the compilePath:"
    print "DEBUG - %s\n" % os.getcwdu()
    if "compilePath" not in os.getcwdu():
        raise Exception("We are not in compilePath.")
    
# Compile the other build.
# No need to assign jsShellName here.
if compileType == "dbg":
    os.chdir("opt-objdir")
    subprocess.call(["../configure", "--enable-optimize", "--disable-debug"])
    compileCopy("opt")
elif compileType == "opt":
    os.chdir("dbg-objdir")
    subprocess.call(["../configure", "--disable-optimize", "--enable-debug"])
    compileCopy("dbg")
else:
    exceptionBadCompileType()

# Change into fuzzPath directory.
os.chdir("../../")

if verbose:
    verbose()
    print "DEBUG - os.getcwdu() should be the fuzzPath:"
    print "DEBUG - %s/" % os.getcwdu()
    print "DEBUG - fuzzPath is: %s\n" % fuzzPath
    #FIXME
    if fuzzPath != os.getcwdu() + "/":
        raise Exception("We are not in fuzzPath.")

# Copy over useful files that are updated in hg fuzzing branch.
if os.name == "posix":
    shutil.copy2(os.path.expanduser(repoFuzzing + "jsfunfuzz/jsfunfuzz.js"), \
                 ".")
    shutil.copy2(os.path.expanduser(repoFuzzing + "jsfunfuzz/analysis.py"), ".")
elif os.name == "nt":
    shutil.copy2(repoFuzzing + "jsfunfuzz/jsfunfuzz.js", ".")
    shutil.copy2(repoFuzzing + "jsfunfuzz/analysis.py", ".")
else:
    exceptionBadOs()

#FIXME
print
print "========================================"
print "!  Fuzzing " + compileType + " " + branchType + " js shell builds now  !"
print "   DATE: " + time.asctime( time.localtime(time.time()) )
print "========================================"
print


# Define the corresponding js-known directories.
jsknown191 = repoFuzzing + "js-known/mozilla-1.9.1/"
jsknown192 = repoFuzzing + "js-known/mozilla-1.9.2/"
# For TM, we use mozilla-central's js-known directories.
jsknownTM = repoFuzzing + "js-known/mozilla-central/"
multiTimedRun = repoFuzzing + "jsfunfuzz/multi_timed_run.py"
multiTimedRunTimeout = "1800"  # Timeout in 1800s or 30mins
jsfunfuzzPath = repoFuzzing + "jsfunfuzz/jsfunfuzz.js"
# Activate JIT fuzzing here, turned on by default.
jsJitSwitch = True
if jsJitSwitch == True:
    jsJit = " -j "
else:
    jsJit = " "

# Commands to simulate bash's `tee`.
tee = subprocess.Popen(["tee", "log-jsfunfuzz"], stdin=subprocess.PIPE)

# Define command for the appropriate OS and branchType.
# POSIX systems include Linux and Mac OS X.
if os.name == "posix":
    posixFuzzCommandPart1 = "python -u " + os.path.expanduser(multiTimedRun) + \
                            " " + multiTimedRunTimeout + " "
    posixFuzzCommandPart2 = " " + fuzzPath + jsShellName + jsJit + \
                            os.path.expanduser(jsfunfuzzPath)
    # Have a different js-known directory for each branchType.
    if branchType == "191":
        fuzzCommand = posixFuzzCommandPart1 + os.path.expanduser(jsknown191) + \
                      posixFuzzCommandPart2
    elif branchType == "192":
        fuzzCommand = posixFuzzCommandPart1 + os.path.expanduser(jsknown192) + \
                      posixFuzzCommandPart2
    elif branchType == "tm":
        fuzzCommand = posixFuzzCommandPart1 + os.path.expanduser(jsknownTM) + \
                      posixFuzzCommandPart2
    else:
        exceptionBadPosixBranchType()()
# NT systems include MozillaBuild on supported Windows platforms.
elif os.name == "nt":
    ntFuzzCommandPart1 = "python -u " + multiTimedRun + " " + \
                         multiTimedRunTimeout + " "
    ntFuzzCommandPart2 = " " + fuzzPath + jsShellName + jsJit + jsfunfuzzPath
    # Have a different js-known directory for each branchType.
    if branchType == "191":
        fuzzCommand = ntFuzzCommandPart1 + jsknown191 + ntFuzzCommandPart2
    elif branchType == "192":
        fuzzCommand = ntFuzzCommandPart1 + jsknown192 + ntFuzzCommandPart2
    elif branchType == "tm":
        fuzzCommand = ntFuzzCommandPart1 + jsknownTM + ntFuzzCommandPart2
    else:
        exceptionBadNtBranchType()()
else:
    exceptionBadOs()

if verbose:
    verbose()
    print "DEBUG - jsShellName is " + jsShellName
    print "DEBUG - fuzzPath + jsShellName is " + fuzzPath + jsShellName
    print "DEBUG - fuzzCommand is " + fuzzCommand
    print
    #FIXME
    
print "=== Performing self-test... ==="
# Create a testfile with the gczeal() function.
subprocess.call(["echo 'gczeal()' > compileTypeTest"], shell=True)
testFileErrorCode = subprocess.call(["./" + jsShellName + " compileTypeTest"], \
    shell=True)
os.remove("compileTypeTest")  # Remove testfile after grabbing the error code.

if verbose:
    verbose()
    print "DEBUG - The error code for debug shells should be 0."
    print "DEBUG - The error code for opt shells should be 3."
    print "DEBUG - The actual error code for " + jsShellName + " now, is: " + \
          str(testFileErrorCode)
    #FIXME

# The error code for debug shells when passing in the gczeal() function should
# be 0.
if compileType == "dbg" and testFileErrorCode != 0:
    print "ERROR: compileType == \"dbg\" and testFileErrorCode != 0"
    print "compileType is: " + compileType
    print "testFileErrorCode is: " + str(testFileErrorCode)
    print
    #FIXME
    raise Exception("The compiled binary is not a debug shell.")
# The error code for optimized shells when passing in the gczeal() function
# should be 3, because they don't have the function compiled in.
elif compileType == "opt" and testFileErrorCode != 3:
    print "ERROR: compileType == \"opt\" and testFileErrorCode != 3"
    print "compileType is: " + compileType
    print "testFileErrorCode is: " + str(testFileErrorCode)
    print
    #FIXME
    raise Exception("The compiled binary is not an optimized shell.")
print "\n=== End of self-test... ===\n"

# Commands to simulate bash's `tee`.
# Start fuzzing the newly compiled builds.
subprocess.call([fuzzCommand], stdout=tee.stdin, shell=True)

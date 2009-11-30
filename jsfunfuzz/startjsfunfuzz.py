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
# November 2009 - 5.x:
#   (version numbers are now obsolete but are added just for fun now)
#   Add 32-bit and 64-bit compilation, patching support. Host of other
#   improvements. Now only supports 1.9.1.x, 1.9.2.x, TM and a future 1.9.3.x.

import sys, os, subprocess, shutil, time, errno, platform

from functionStartjsfunfuzz import *

supportedBranches = "[191|192|tm]"
#193support
#supportedBranches = "[191|192|193|tm]"
supportedBranchFOO = []
# Add supported branches here.
supportedBranchFOO.append('191')
supportedBranchFOO.append('192')
#193support
#supportedBranchFOO.append('193')
supportedBranchFOO.append('tm')

verbose = True  # Turn this to True to enable verbose output for debugging.

# Accept 32-bit and 64-bit parameters only.
if (sys.argv[1] == "32") or (sys.argv[1] == "64"):
    archNum = sys.argv[1]
else:
    error(supportedBranches)
    print "Your archNum variable is \'" + archNum + "\'"
    raise Exception("Choose only to compile either 32-bit or 64-bit binaries."+
                    " Note that this choice only applies to Mac OS X 10.6.x, "+
                    "every other operating system will compile in 32-bit.")

# Accept dbg and opt parameters for compileType only.
if (sys.argv[2] == "dbg") or (sys.argv[2] == "opt"):
    compileType = sys.argv[2]
else:
    error(supportedBranches)
    print "Your compileType variable is \'" + compileType + "\'"
    exceptionBadCompileType()


# Accept appropriate parameters for branchType.
if (sys.argv[3] == "191") or (sys.argv[3] == "192") or (sys.argv[3] == "tm"):
#193support
#if (sys.argv[3] == "191") or (sys.argv[3] == "192") or (sys.argv[3] == "192")\
#    or (sys.argv[3] == "tm"):
    branchType = sys.argv[3]
else:
    error(supportedBranches)
    print "Your branchType variable is \'" + branchType + "\'"
    raise Exception("Please double-check your branchType from " + \
                    supportedBranches + ".")

if (sys.argv[1] == "64") and (sys.argv[3] == "191"):
    raise Exception("64-bit compilation is not supported on 1.9.1 branch.")


# Definitions of the different repository and fuzzing locations.
if os.name == "posix":
    def locations():
        repoFuzzing = "~/fuzzing/"     # Location of the fuzzing repository.
        repo191 = "~/mozilla-1.9.1/"   # Location of the 1.9.1 repository.
        repo192 = "~/mozilla-1.9.2/"   # Location of the 1.9.2 repository.
        #193support
        #repo193 = "~/mozilla-1.9.3/"   # Location of the 1.9.3 repository.
        repoTM = "~/tracemonkey/"      # Location of the tracemonkey repository
        fuzzPathStart = "~/Desktop/jsfunfuzz-" # Start of the fuzzing directory
        return repoFuzzing, repo191, repo192, repoTM, fuzzPathStart
        #193support
        #return repoFuzzing, repo191, repo192, repo193, repoTM, fuzzPathStart
elif os.name == "nt":
    def locations():
        # ~ is not used because in XP, ~ contains spaces in
        # "Documents and Settings". This file assumes the repositories to be in
        # the root directory of the same drive as this file.
        repoFuzzing = "/fuzzing/"    # Location of the fuzzing repository.
        repo191 = "/mozilla-1.9.1/"  # Location of the 1.9.1 repository.
        repo192 = "/mozilla-1.9.2/"  # Location of the 1.9.2 repository.
        #193support
        #repo193 = "/mozilla-1.9.3/"   # Location of the 1.9.3 repository.
        repoTM = "/tracemonkey/"     # Location of the tracemonkey repository.
        fuzzPathStart = "/jsfunfuzz-"   # Start of the fuzzing directory.
        return repoFuzzing, repo191, repo192, repoTM, fuzzPathStart
        #193support
        #return repoFuzzing, repo191, repo192, repo193, repoTM, fuzzPathStart
else:
    exceptionBadOs()

repoFuzzing, repo191, repo192, repoTM, fuzzPathStart = locations()
#193support
#repoFuzzing, repo191, repo192, repo193, repoTM, fuzzPathStart = locations()

if verbose:
    verboseMsg()
    print "DEBUG - repoFuzzing, repo191, repo192, repoTM, fuzzPathStart are:"
    #193support
    #print "DEBUG - repoFuzzing, repo191, repo192, repo193, repoTM, " + \
    #    "fuzzPathStart are:"
    print "DEBUG - %s" % ", ".join(locations())

# Expand the ~ folder on Linux/Mac.
fuzzPathRaw = fuzzPathStart + compileType + "-" + archNum + "-" + branchType \
              + "/"
if os.name == "posix":
    fuzzPath = os.path.expanduser(fuzzPathRaw)
elif os.name == "nt":
    fuzzPath = fuzzPathRaw
else:
    exceptionBadOs()

# Save the current directory as a variable.
currDir = os.getcwd()

# Note and attach the numbers and hashes of the current changeset in the
# fuzzPath.
if os.name == "posix":
    if branchType == "191":
        os.chdir(os.path.expanduser(repo191))
        fuzzPath = hgHashAddToFuzzPath(fuzzPath)
    elif branchType == "192":
        os.chdir(os.path.expanduser(repo192))
        fuzzPath = hgHashAddToFuzzPath(fuzzPath)
    #193support
    #elif branchType == "193":
    #    os.chdir(os.path.expanduser(repo193))
    #    fuzzPath = hgHashAddToFuzzPath(fuzzPath)
    elif branchType == "tm":
        os.chdir(os.path.expanduser(repoTM))
        fuzzPath = hgHashAddToFuzzPath(fuzzPath)
elif os.name == "nt":
    if branchType == "191":
        os.chdir(repo191)
        fuzzPath = hgHashAddToFuzzPath(fuzzPath)
    elif branchType == "192":
        os.chdir(repo192)
        fuzzPath = hgHashAddToFuzzPath(fuzzPath)
    #193support
    #elif branchType == "193":
    #    os.chdir(repo193)
    #    fuzzPath = hgHashAddToFuzzPath(fuzzPath)
    elif branchType == "tm":
        os.chdir(repoTM)
        fuzzPath = hgHashAddToFuzzPath(fuzzPath)
else:
    exceptionBadOs()

fuzzPath += "/"

# Switch back to original directory.
if os.name == "posix":
    os.chdir(os.path.expanduser(currDir))
elif os.name == "nt":
    os.chdir(currDir)
else:
    exceptionBadOs()

# Create the fuzzing folder.
try:
    # Rename directory if patches are applied, accept up to 2 patches.
    if len(sys.argv) >= 6 and \
      (sys.argv[4] == 'patch' or sys.argv[6] == 'patch'):
        fuzzPath += "patched/"
    os.makedirs(fuzzPath)
except OSError:
    error(supportedBranches)
    raise Exception("The fuzzing path at \'" + fuzzPath + "\' already exists!")

# Change to the fuzzing directory.
os.chdir(fuzzPath)

# Copy the entire js tree to the fuzzPath.
if os.name == "posix":
    if branchType == "191":
        posixCopyJsTree(repo191)
    elif branchType == "192":
        posixCopyJsTree(repo192)
    #193support
    #elif branchType == "193":
    #    posixCopyJsTree(repo193)
    elif branchType == "tm":
        posixCopyJsTree(repoTM)
    else:
        exceptionBadPosixBranchType()()
elif os.name == "nt":
    if branchType == "191":
        ntCopyJsTree(repo191)
    elif branchType == "192":
        ntCopyJsTree(repo192)
    #193support
    #elif branchType == "193":
    #    ntCopyJsTree(repo193)
    elif branchType == "tm":
        ntCopyJsTree(repoTM)
    else:
        exceptionBadNtBranchType()()
else:
    exceptionBadOs()

# Change into compilation directory.
os.chdir("compilePath")

patchReturnCode = 0
patchReturnCode2 = 0
# Patch the codebase if specified, accept up to 2 patches.
if len(sys.argv) < 8 and len(sys.argv) >= 6 and sys.argv[4] == 'patch':
    patchReturnCode = subprocess.call(["patch -p3 < " + sys.argv[5]],
        shell=True)

if len(sys.argv) >= 8 and sys.argv[6] == 'patch':
    patchReturnCode2 = subprocess.call(["patch -p3 < " + sys.argv[7]],
        shell=True)

if patchReturnCode == 1 or patchReturnCode2 == 1:
    raise Exception("Patching failed.")

# Sniff platform and run different autoconf types:
if os.name == "posix":
    if os.uname()[0] == "Darwin":
        subprocess.call(["autoconf213"])
    elif os.uname()[0] == "Linux":
        subprocess.call(["autoconf2.13"])
elif os.name == "nt":
    subprocess.call(["sh", "autoconf-2.13"])
else:
    exceptionBadOs()

# Sniff for 10.6, as it compiles 64-bit by default and we want to compile
# 32-bit by default for now.
macVer, _, _ = platform.mac_ver()
macVer = float('.'.join(macVer.split('.')[:2]))

# Create objdirs within the compilePaths.
os.mkdir("dbg-objdir")
os.mkdir("opt-objdir")
os.chdir(compileType + "-objdir")

# Compile the first build.
if compileType == "dbg":
    dbgCompile(macVer, archNum)
elif compileType == "opt":
    optCompile(macVer, archNum)
else:
    exceptionBadCompileType()

jsShellName = compileCopy(branchType, compileType, archNum)

# Change into compilePath directory for the opt build.
os.chdir("../")

if verbose:
    verboseMsg()
    print "DEBUG - This should be the compilePath:"
    print "DEBUG - %s\n" % os.getcwdu()
    if "compilePath" not in os.getcwdu():
        raise Exception("We are not in compilePath.")

# Compile the other build.
# No need to assign jsShellName here.
if compileType == "dbg":
    os.chdir("opt-objdir")
    optCompile(macVer, archNum)
    compileCopy(branchType, "opt", archNum)
elif compileType == "opt":
    os.chdir("dbg-objdir")
    dbgCompile(macVer, archNum)
    compileCopy(branchType, "dbg", archNum)
else:
    exceptionBadCompileType()

# Change into fuzzPath directory.
os.chdir("../../")

if verbose:
    verboseMsg()
    print "DEBUG - os.getcwdu() should be the fuzzPath:"
    print "DEBUG - %s/" % os.getcwdu()
    print "DEBUG - fuzzPath is: %s\n" % fuzzPath
    #FIXME
    if os.name == "posix":
        if fuzzPath != (os.getcwdu() + "/"):
            raise Exception("We are not in fuzzPath.")
    elif os.name == "nt":
        if fuzzPath[1:] != (os.getcwdu() + "/")[3:]:  # Ignore drive letter.
            raise Exception("We are not in fuzzPath.")
    else:
        exceptionBadOs()

# Copy over useful files that are updated in hg fuzzing branch.
if os.name == "posix":
    shutil.copy2(os.path.expanduser(repoFuzzing + "jsfunfuzz/jsfunfuzz.js"), \
                 ".")
    shutil.copy2(os.path.expanduser(repoFuzzing + "jsfunfuzz/analysis.py"), \
                 ".")
elif os.name == "nt":
    shutil.copy2(repoFuzzing + "jsfunfuzz/jsfunfuzz.js", ".")
    shutil.copy2(repoFuzzing + "jsfunfuzz/analysis.py", ".")
else:
    exceptionBadOs()


print '''
=============================================
!  Fuzzing %s %s %s js shell builds now  !
   DATE: %s
=============================================
''' % (archNum + "-bit", compileType, branchType,
       time.asctime( time.localtime(time.time()) ))


# Define the corresponding js-known directories.
jsknown191 = repoFuzzing + "js-known/mozilla-1.9.1/"
jsknown192 = repoFuzzing + "js-known/mozilla-1.9.2/"
#193support
#jsknown193 = repoFuzzing + "js-known/mozilla-1.9.3/"
# For TM, we use mozilla-central's js-known directories.
jsknownTM = repoFuzzing + "js-known/mozilla-central/"
multiTimedRun = repoFuzzing + "jsfunfuzz/multi_timed_run.py"
multiTimedRunTimeout = "10"
# Activate JIT fuzzing here, turned on by default.
jsJitSwitch = True
if jsJitSwitch == True:
    jsJit = " -j "
else:
    jsJit = " "
valgrindSupport = False  # Set this to True for valgrind fuzzing.
if valgrindSupport == True:
    multiTimedRunTimeout = "1000"
# Activate compareJIT here, turned on by default.
jsCompareJITSwitch = True
if jsCompareJITSwitch == True and valgrindSupport != True:
    jsCompareJIT = " --comparejit "
else:
    jsCompareJIT = " "

# Commands to simulate bash's `tee`.
tee = subprocess.Popen(["tee", "log-jsfunfuzz"], stdin=subprocess.PIPE)

# Define command for the appropriate OS and branchType.
# POSIX systems include Linux and Mac OS X.
if os.name == "posix":
    posixFuzzCommandPart1 = "python -u " + os.path.expanduser(multiTimedRun) +\
                            " " + jsCompareJIT + multiTimedRunTimeout + " "
    posixFuzzCommandPart2 = " " + fuzzPath + jsShellName + jsJit
    if valgrindSupport == True:
        posixFuzzCommandPart2 = " valgrind" + posixFuzzCommandPart2
    # Have a different js-known directory for each branchType.
    if branchType == "191":
        fuzzCommand = posixFuzzCommandPart1 + os.path.expanduser(jsknown191) +\
                      posixFuzzCommandPart2
    elif branchType == "192":
        fuzzCommand = posixFuzzCommandPart1 + os.path.expanduser(jsknown192) +\
                      posixFuzzCommandPart2
    #193support
    #elif branchType == "193":
    #    fuzzCommand = posixFuzzCommandPart1 + os.path.expanduser(jsknown193) +\
    #                  posixFuzzCommandPart2
    elif branchType == "tm":
        fuzzCommand = posixFuzzCommandPart1 + os.path.expanduser(jsknownTM) + \
                      posixFuzzCommandPart2
    else:
        exceptionBadPosixBranchType()()
# NT systems include MozillaBuild on supported Windows platforms.
elif os.name == "nt":
    ntFuzzCommandPart1 = "python -u " + multiTimedRun + " " + jsCompareJIT + \
                         multiTimedRunTimeout + " "
    ntFuzzCommandPart2 = " " + fuzzPath + jsShellName + jsJit
    # Have a different js-known directory for each branchType.
    if branchType == "191":
        fuzzCommand = ntFuzzCommandPart1 + jsknown191 + ntFuzzCommandPart2
    elif branchType == "192":
        fuzzCommand = ntFuzzCommandPart1 + jsknown192 + ntFuzzCommandPart2
    #193support
    #elif branchType == "193":
    #    fuzzCommand = ntFuzzCommandPart1 + jsknown193 + ntFuzzCommandPart2
    elif branchType == "tm":
        fuzzCommand = ntFuzzCommandPart1 + jsknownTM + ntFuzzCommandPart2
    else:
        exceptionBadNtBranchType()()
else:
    exceptionBadOs()

if verbose:
    verboseMsg()
    print "DEBUG - jsShellName is " + jsShellName
    print "DEBUG - fuzzPath + jsShellName is " + fuzzPath + jsShellName
    print "DEBUG - fuzzCommand is " + fuzzCommand
    print
    #FIXME

test32or64bit(jsShellName, macVer, archNum)

print "\n=== Performing self-test... ==="
# Create a testfile with the gczeal() function.
if os.name == "posix":
    subprocess.call(["echo 'gczeal()' > compileTypeTest"], shell=True)
    testFileErrorCode = subprocess.call(["./" + jsShellName + \
                                         " compileTypeTest"], shell=True)

elif os.name == "nt":
    subprocess.call(["echo gczeal() > compileTypeTest"], shell=True)
    testFileErrorCode = subprocess.call([jsShellName + " compileTypeTest"], \
        shell=True)
else:
    exceptionBadOs()
os.remove("compileTypeTest")  # Remove testfile after grabbing the error code.

if verbose:
    verboseMsg()
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

# Try to remove objdirs if they are empty. Both should not be empty.
try:
    os.rmdir("compilePath/dbg-objdir/")
except OSError, err:
    if err.errno == errno.ENOTEMPTY:
        pass
    else:
        raise

try:
    os.rmdir("compilePath/opt-objdir/")
except OSError, err:
    if err.errno == errno.ENOTEMPTY:
        pass
    else:
        raise

# Commands to simulate bash's `tee`.
# Start fuzzing the newly compiled builds.
subprocess.call([fuzzCommand], stdout=tee.stdin, shell=True)

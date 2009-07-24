#!/usr/bin/env python

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
#   Python rewrite - only 1.9.1.x, TM and v8 planned for support. 1.9.0.x is
#   becoming obsolete in 5.5 months, mozTrunk is rarely fuzzed in favour of TM,
#   JavaScriptCore doesn't feel like a significant competing engine, and Safari
#   uses its own Nitro engine.
#
# Note:
#   If something screws up, trash the entire existing
#       ~/Desktop/jsfunfuzz-$compileType-$branchType folder.
#
# Receive user input on compileType and branchType.
#   compileType can be debug or opt.
#   branchType can be Gecko 1.9.1.x, TM or v8 engines.

import sys, os, subprocess, shutil
from time import gmtime, strftime

###############
#  Variables  #
###############

verbose = True  # Turn this to True to enable verbose output for debugging.
def verbose():
    print
    print "DEBUG - output:"
supportedBranches = "[191|tm|v8]"  # 1.9.2 support can be easily added later. Implement FIXMEFOR192 ?

# FIXME: Use optparse here.

# The corresponding CLI requirements should be input, else output this error.
def error():
    print
    print "=========="
    print "| Error! |"
    print "=========="
    print
    print "General usage: ./run-jsfunfuzz.py [dbg|opt] " + supportedBranches
    print


# Accept dbg and opt parameters for compileType only.
if (sys.argv[1] == "dbg") or (sys.argv[1] == "opt"):
    compileType = sys.argv[1]
else:
    error()
    print "Your compileType variable is \'" + compileType + "\'"
    print "Error reason: Only \'dbg\' or \'opt\' are accepted as compileType.\n"
    quit()


# Accept appropriate parameters for branchType.
# FIXMEFOR192: Add 192 support here once the 1.9.2 branch is created.
if (sys.argv[2] == "191") or (sys.argv[2] == "tm") or (sys.argv[2] == "v8"):
    branchType = sys.argv[2]
else:
    error()
    print "Your branchType variable is \'" + branchType + "\'"
    print "Error reason: Please double-check your branchType " + \
    supportedBranches + ".\n"
    quit()


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
        # "Documents and Settings".
        repoFuzzing = "/c/fuzzing/"    # Location of the fuzzing repository.
        repo191 = "/c/mozilla-1.9.1/"  # Location of the 1.9.1 repository.
        repo192 = "/c/mozilla-1.9.2/"  # Location of the 1.9.2 repository.
        repoTM = "/c/tracemonkey/"     # Location of the tracemonkey repository.
        fuzzPathStart = "/c/jsfunfuzz-"   # Start of the fuzzing directory.
        return repoFuzzing, repo191, repo192, repoTM, fuzzPathStart
else:
    raise Exception("Unknown OS - Platform is unsupported.")
    
repoFuzzing, repo191, repo192, repoTM, fuzzPathStart = locations()

if verbose:
    verbose()
    print "DEBUG - repoFuzzing, repo191, repo192, repoTM, fuzzPathStart are:"
    print "DEBUG - " + ", ".join(locations())


# Expand the ~ folder on Linux/Mac.
if os.name == "posix":
    fuzzPath = os.path.expanduser(fuzzPathStart + compileType + "-" + \
                                  branchType + "/")

# Create the fuzzing folder.
try:
    os.makedirs(fuzzPath)
except OSError:
    error()
    print "Error reason: The fuzzing path at \'" + fuzzPath + \
    "\' already exists! Exiting ...\n"
    # FIXME: Use shell's form of read. `value = raw_input(optional_prompt)`
    # print "Do you want to remove it? (y/n)"   # FIXME Suggested removal.
                                                # Use shutil.rmtree ...
    quit()

# Change to the fuzzing directory.
os.chdir(fuzzPath)

# Copy the entire js tree to the fuzzPath.
if os.name == "posix":
    if branchType == "191":
        shutil.copytree(os.path.expanduser(repo191 + "js/src/"),"compilePath")
    elif branchType == "192":
        shutil.copytree(os.path.expanduser(repo192 + "js/src/"),"compilePath")
    elif branchType == "tm":
        shutil.copytree(os.path.expanduser(repoTM + "js/src/"),"compilePath")
elif os.name == "nt":
    shutil.copytree("/c/mozilla-1.9.1/js/src/","compilePath") # FIXME write the proper NT paths. without expanduser, basically. Also, consider copytree2 if any.

os.chdir("compilePath")

# Sniff platform and run different autoconf types:
if os.name == "posix":
    if os.uname()[0] == "Darwin":
        subprocess.call("autoconf213")
    elif os.uname()[0] == "Linux":
        subprocess.call("autoconf2.13")
elif os.name == "nt":
    subprocess.call("autoconf-2.13")

# Create objdirs within the compilePaths.
os.mkdir("dbg-objdir")
os.mkdir("opt-objdir")


# Compile the first build.
if compileType == "dbg":
    os.chdir("dbg-objdir")
    subprocess.call(["../configure", "--disable-optimize", "--enable-debug"])
elif compileType == "opt":
    os.chdir("opt-objdir")
    subprocess.call(["../configure", "--enable-optimize", "--disable-debug"])

def compileCopy(dbgOpt):
    # Run make using 2 cores.
    subprocess.call(["make", "-j2"])
    
    # Sniff platform and rename executable accordingly:
    if os.name == "posix":
        shellName = "js-" + dbgOpt + "-" + branchType + "-" + \
                    os.uname()[0].lower()
    elif os.name == "nt":
        shellName = "js-" + dbgOpt + "-" + branchType + "-" + os.name.lower()
    
    # Copy js executable out into fuzzPath.
    shutil.copy2("js","../../" + shellName)
    
    return shellName

jsShellName = compileCopy(compileType)

# Change into compilePath directory for the opt build.
os.chdir("../")

if verbose:
    verbose()
    print "DEBUG - This should be the compilePath:"
    print "DEBUG - " + os.getcwdu()
    
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

# Change into fuzzPath directory.
os.chdir("../../")

if verbose:
    verbose()
    print "DEBUG - This should be the fuzzPath:"
    print "DEBUG - " + os.getcwdu()


# FIXME v8 checkout.

# Copy over useful files that are updated in hg fuzzing branch.
if os.name == "posix":
    shutil.copy2(os.path.expanduser(repoFuzzing + "jsfunfuzz/jsfunfuzz.js"), ".")
    shutil.copy2(os.path.expanduser(repoFuzzing + "jsfunfuzz/analysis.sh"), ".")
elif os.name == "nt":
    shutil.copy2(repoFuzzing + "jsfunfuzz/analysis.sh", ".")

print
print "============================================"
print "!  Fuzzing " + compileType + " " + branchType + " js shell builds now  !"
print "   DATE: " + strftime("%a, %d %b %Y %H:%M:%S +0000 %Z", gmtime())
# FIXME: Dates look stupid.
print "============================================"
print


# FIXME: of course have the 191 version of jsknownTM - sniff platform again. what about 192?
jsknownTM = repoFuzzing + "js-known/mozilla-central/"  # We use mozilla-central's js-known directories.
# Start fuzzing the newly compiled builds.
if verbose:
    print "jsShellName is " + jsShellName
    print "fuzzPath + jsShellName is " + fuzzPath + jsShellName
    print "python", "-u", \
                os.path.expanduser(repoFuzzing + "jsfunfuzz/multi_timed_run.py"), "1800", \
                os.path.expanduser(jsknownTM), fuzzPath + jsShellName, \
                "-j", os.path.expanduser(repoFuzzing + "jsfunfuzz/jsfunfuzz.js")
subprocess.call(["python", "-u", \
                os.path.expanduser(repoFuzzing + "jsfunfuzz/multi_timed_run.py"), "1800", \
                os.path.expanduser(jsknownTM), fuzzPath + jsShellName, \
                "-j", os.path.expanduser(repoFuzzing + "jsfunfuzz/jsfunfuzz.js")], \
                stdout=open("log-jsfunfuzz", "w"))
# FIXME: Implement 191, tm and v8 fuzzing for the above which right now is only hardcoded for tm. Works though. :) EDIT - 191 works too? change js-known to 191
# FIXME: I want to pipe stdout both to console output as well as to the file, just like the `tee` command.  stdout=subprocess.Popen(['tee', ...], stdin=subprocess.PIPE).stdin; of course
# FIXME: Implement the time command like in shell to the above. time.time then subtraction
# FIXME: Port above to windows. Basically take out expanduser?
# FIXME: Move paths to another place above.
# FIXME: make use of analysis.sh somewhere, not necessarily here.
# FIXME: Ensure debug builds are debug builds and opt builds are opt! Add unit test? test gczeal(2) - js-dbg should return nothing while opt should return a referenceerror
# FIXME: cleanup multiple elifs to if.. return. See below.
#>>> config = {}
#>>> def foo():
#...     config['boom'] = 'BANG'
#...     config['wat'] = 'YES'
#... 
#>>> def bar():
#...     config['boom'] = 'AAARGH'
#...     config['wat'] = 'NO'
#... 
#>>> {'a': foo, 'b': bar}['a']()
#>>> print config
#{'wat': 'YES', 'boom': 'BANG'}
#>>> {'a': foo, 'b': bar}['b']()
#>>> print config
#{'wat': 'NO', 'boom': 'AAARGH'}
#>>> 
#time python -u ~/fuzzing/jsfunfuzz/multi_timed_run.py 1800 ~/fuzzing/js-known/mozilla-central/ ~/Desktop/jsfunfuzz-$compileType-$branchType/js-$compileType-$branchType-intelmac -j ~/fuzzing/jsfunfuzz/jsfunfuzz.js | tee ~/Desktop/jsfunfuzz-$compileType-$branchType/log-jsfunfuzz

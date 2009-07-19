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
#   becoming obsolete in 5.5 months, mozTrunk is rarely fuzzed in favour of TM
#   and JavaScriptCore simply isn't a significant competing engine, and Safari
#   uses its own Nitro engine.
# 
# Note:
#   If something screws up, trash the entire existing
#       ~/Desktop/jsfunfuzz-$compileType-$branchType folder.
# 
# Receive user input on compileType and branchType.
#   compileType can be debug or opt.
#   branchType can be Gecko 1.9.1.x, TM or v8 engines.

import sys, os, subprocess

# The corresponding CLI requirements should be input, else output this error.
def error():
    print
    print "=========="
    print "| Error! |"
    print "=========="
    print
    print "Usage: ./run-jsfunfuzz.py [dbg|opt] [191|tm|v8]"
    print

# Detect platform and set appropriate fuzzing path.
if os.name == "posix":
    startPath = "~/Desktop/jsfunfuzz-"
elif os.name == "nt":
    startPath = "/c/jsfunfuzz-"
else:
    print "\nPlatform is not supported.\n"
    quit()

# Accept dbg and opt parameters for compileType only.
if (sys.argv[1] == "dbg") or (sys.argv[1] == "opt"):
    compileType = sys.argv[1]
else:
    error()
    print "Error reason: Only \'dbg\' or \'opt\' are accepted as compileType.\n"
    quit()



branchType = sys.argv[2]

fuzzPath = os.path.expanduser(startPath + compileType + "-" + branchType)

#print fuzzDir
print fuzzPath
#os.makedirs(unixFuzzPath)
#os.chdir(unixFuzzPath)
subprocess.call(["ls"])
print "boo"

if os.name == "posix":
    if os.uname()[0] == "Darwin":
        print "This is Mac."
    if os.uname()[0] == "Linux":
        print "This is Linux."
if os.name == "nt":
    print "This is Windows."
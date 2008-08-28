# !/bin/bash
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
# end-April 2008 - 1.0, 1.1:
# 	Initial idea, previously called ./jsfunfuzz-moz18branch-start-intelmac
# June 2008 - 2.0:
# 	Rewritten from scratch to support the new hg fuzzing branch.
# end-August 2008 - 3.0:
# 	Rewritten from scratch again to support command-line inputs and
# 	consolidate all existing jsfunfuzz bash scripts.
# 
# Note:
#   If something screws up, trash the entire existing
#       ~/Desktop/jsfunfuzz-$compileType-$branchType folder.
# 
# Receive user input on compileType and branchType.
#   compileType can be debug or opt.
#   branchType can be Gecko 1.8.1.x, 1.9.0.x, 1.9.1.x branches, or the trunk.
compileType=$1
branchType=$2

echo
echo 'compileFuzz-jsfunfuzz.sh v3.0 by Gary Kwong';
echo ' - for use with jsfunfuzz';

# Checks for a second parameter input.

if [ "$2" = "" ]
    then
        echo
        echo 'usage: ./compileFuzz-jsfunfuzz.sh [dbg|opt] [181|190|191|trunk]';
        echo
        exit 0;
fi

# Determine actions based on first parameter, compileType.

case $compileType in
    "dbg" ) ;;
    "opt" ) ;;
    *     )
        echo
        echo 'usage: ./compileFuzz-jsfunfuzz.sh [dbg|opt] [181|190|191|trunk]'
        echo
        exit 0;;
esac

# Determine actions based on second parameter, branchType.

case $branchType in
    "181"   ) ;;
    "190"   ) ;;
    "191"   ) ;;
    "trunk" ) ;;
    *       )
        echo
        echo 'usage: ./compileFuzz-jsfunfuzz.sh [dbg|opt] [181|190|191|trunk]'
        echo
        exit 0;;
esac

echo
echo 'Have you deleted or renamed the existing directory?'
echo '(You should do so before you enter "yes".)'
echo -n 'Answer (yes?): '
read delDecision
if [ $delDecision = "yes" ]
    then
        echo
        date
        echo
    else
        echo
        exit 0;
fi

# This line will overwrite your existing directory's files.
mkdir -p ~/Desktop/jsfunfuzz-$compileType-$branchType
cd ~/Desktop/jsfunfuzz-$compileType-$branchType

# Compile a js shell build, duplicate the source, then move the shell out.

# This line will overwrite your existing directory's files.
mkdir -p debug-$branchType opt-$branchType
cd debug-$branchType


# Gecko 1.8.1.x and 1.9.0.x are in CVS.

if ( [ $branchType = "181" ] || [ $branchType = "190" ] ) then
    export CVSROOT=:pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot
    
    # Check out CVS source files depending on parameters.
    if [ $compileType = "181" ]
        then
            cvs co -r MOZILLA_1_8_BRANCH -l mozilla/js/src mozilla/js/src/fdlibm
            cvs co -l mozilla/js/src/config mozilla/js/src/editline
        else
            cvs co -l mozilla/js/src mozilla/js/src/config mozilla/js/src/editline mozilla/js/src/fdlibm
    fi
    cd ..
    
    # Debug builds, keeping the debug source code directory,
    #   in case gdb is needed for symbols.
    cp -r debug-$branchType/* opt-$branchType/
    cd debug-$branchType/mozilla/js/src
    # |Make| sometimes screws up when compiling a build using 2 jobs.
    make -f Makefile.ref
    cd Darwin_DBG.OBJ
    cp js ../../../../../js-dbg-$branchType-intelmac
    cd ../../../../../
    
    # Opt build, removing the opt source code directory.
    cd opt-$branchType/mozilla/js/src
    # |Make| sometimes screws up when compiling a build using 2 jobs.
    make BUILD_OPT=1 -f Makefile.ref
    cd Darwin_OPT.OBJ
    cp js ../../../../../js-opt-$branchType-intelmac
    cd ../../../../../
    rm -r opt-$branchType
fi


# Gecko 1.9.1.x and the trunk are in Mercurial.

if ( [ $branchType = "191" ] || [ $branchType = "trunk" ] )
    then
        # 
        # NOTE: Gecko 1.9.1.x has not yet branched from the trunk.
        # 
        # This assumes you have an updated mozilla-central directory.
        cp -r ~/mozilla-central/js/src/ .
        cd ..
        
        # Debug builds, keeping the debug source code directory,
        #   in case gdb is needed for symbols.
        cp -r debug-$branchType/* opt-$branchType/
        cd debug-$branchType
        # |Make| sometimes screws up when compiling a build using 2 jobs.
        make -f Makefile.ref
        cd Darwin_DBG.OBJ
        cp js ../../js-dbg-$branchType-intelmac
        cd ../../
        
        # Opt build, removing the opt source code directory.
        cd opt-$branchType
        # |Make| sometimes screws up when compiling a build using 2 jobs.
        make BUILD_OPT=1 -f Makefile.ref
        cd Darwin_OPT.OBJ
        cp js ../../js-opt-$branchType-intelmac
        cd ../../
        rm -r opt-$branchType
fi

cd ~/Desktop/jsfunfuzz-$compileType-$branchType

# Copy over useful files that are updated in hg fuzzing branch.
cp ~/fuzzing/jsfunfuzz/jsfunfuzz.js .
cp ~/fuzzing/jsfunfuzz/analysis.sh .

echo
echo '============================================'
echo -n '!  Fuzzing '
echo -n $compileType
echo -n ' '
echo -n $branchType
echo ' js shell builds now  !'
echo -n '   DATE: '
date
echo '============================================'
echo

# Start fuzzing the newly compiled builds.
time python -u ~/fuzzing/jsfunfuzz/multi_timed_run.py 1800 ~/Desktop/jsfunfuzz-$compileType-$branchType/js-$compileType-$branchType-intelmac ~/fuzzing/jsfunfuzz/jsfunfuzz.js | tee ~/Desktop/jsfunfuzz-$compileType-$branchType/log-jsfunfuzz

echo
date
echo
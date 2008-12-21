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
# April 2008 - 1.x:
# 	Initial idea, previously called ./jsfunfuzz-moz18branch-start-intelmac
# June 2008 - 2.x:
# 	Rewritten from scratch to support the new hg fuzzing branch.
# August 2008 - 3.0.x:
# 	Rewritten from scratch again to support command-line inputs and
# 	consolidate all existing jsfunfuzz bash scripts.
# September 2008 - 3.1.x:
# 	Support fuzzing v8 engine.
# mid-December 2008 - 3.2.x:
#   Supports 1.9.1.x branch. Rip out 1.8.1.x code.
# 
# Note:
#   If something screws up, trash the entire existing
#       ~/Desktop/jsfunfuzz-$compileType-$branchType folder.
# 
# Receive user input on compileType and branchType.
#   compileType can be debug or opt.
#   branchType can be Gecko 1.9.0.x, 1.9.1.x branches, the trunk, or the v8 engine.

compileType=$1
branchType=$2

echo
echo 'compileFuzz-jsfunfuzz.sh v3.2.1 by Gary Kwong';
echo ' - for use with jsfunfuzz';
echo
echo 'NOTE1: You must have a ~/fuzzing/ directory.';
echo 'NOTE2: You must have a mozilla hg repository in ~/mozilla-1.9.1/';
echo '         and/or in ~/mozilla-central/ for moz191 or mozTrunk to work properly.';

# Checks for a second parameter input.

if [ "$2" = "" ]
    then
        echo
        echo 'usage: ./compileFuzz-jsfunfuzz.sh [dbg|opt] [moz190|moz191|mozTrunk|tm|v8]';
        echo
        exit 0;
fi

# Determine actions based on first parameter, compileType.

case $compileType in
    "dbg" ) ;;
    "opt" ) ;;
    *     )
        echo
        echo 'usage: ./compileFuzz-jsfunfuzz.sh [dbg|opt] [moz190|moz191|mozTrunk|tm|v8]'
        echo
        exit 0;;
esac

# Determine actions based on second parameter, branchType.

case $branchType in
    "moz190"   ) ;;
    "moz191"   ) ;;
    "mozTrunk" ) ;;
    "tm" ) ;;
    "v8" ) ;;
    *       )
        echo
        echo 'usage: ./compileFuzz-jsfunfuzz.sh [dbg|opt] [moz190|moz191|mozTrunk|tm|v8]'
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


# Gecko 1.9.0.x is in CVS.

if ( [ $branchType = "moz190" ] ) then
    export CVSROOT=:pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot
    cvs co -l mozilla/js/src mozilla/js/src/config mozilla/js/src/editline mozilla/js/src/fdlibm
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

# Gecko 1.9.1.x is in Mercurial and has a different compile method from 1.9.0.x.

if ( [ $branchType = "moz191" ] ) then
    cp -r ~/mozilla-1.9.1/js/src/ .
    cd ..
    
    # Debug builds.
    cd debug-$branchType
    autoconf213
    mkdir dbg-objdir
    cd dbg-objdir
    ../configure --disable-optimize --enable-debug
    make
    cp js ../../js-dbg-$branchType-intelmac
    cd ..
    
    # Opt builds.
    mkdir opt-objdir
    cd opt-objdir
    ../configure --enable-optimize --disable-debug
    make
    cp js ../../js-opt-$branchType-intelmac
    cd ../../
    rmdir opt-$branchType  # Obsoleted by new compile method.
fi

# Trunk is in Mercurial and has a different compile method from 1.9.0.x.

if ( [ $branchType = "mozTrunk" ] ) then
    cp -r ~/mozilla-central/js/src/ .
    cd ..
    
    # Debug builds.
    cd debug-$branchType
    autoconf213
    mkdir dbg-objdir
    cd dbg-objdir
    ../configure --disable-optimize --enable-debug
    make
    cp js ../../js-dbg-$branchType-intelmac
    cd ..
    
    # Opt builds.
    mkdir opt-objdir
    cd opt-objdir
    ../configure --enable-optimize --disable-debug
    make
    cp js ../../js-opt-$branchType-intelmac
    cd ../../
    rmdir opt-$branchType  # Obsoleted by new compile method.
fi

# TraceMonkey is in a separate branch from trunk and has a different compile method from 1.9.0.x.

if ( [ $branchType = "tm" ] ) then
    cp -r ~/tracemonkey/js/src/ .
    cd ..
    
    # Debug builds.
    cd debug-$branchType
    autoconf213
    mkdir dbg-objdir
    cd dbg-objdir
    ../configure --disable-optimize --enable-debug
    make
    cp js ../../js-dbg-$branchType-intelmac
    cd ..
    
    # Opt builds.
    mkdir opt-objdir
    cd opt-objdir
    ../configure --enable-optimize --disable-debug
    make
    cp js ../../js-opt-$branchType-intelmac
    cd ../../
    rmdir opt-$branchType  # Obsoleted by new compile method.
fi


# Google Chrome uses the v8 Javascript engine.

if ( [ $compileType = "dbg" ] && [ $branchType = "v8" ] ) then
	# 
    # SVN checks out five times, it seems to consistently error out 1 or 2 times.
    # Sample:
    # svn: REPORT request failed on '/svn/!svn/vcc/default'
	# svn: REPORT of '/svn/!svn/vcc/default': 200 OK (http://v8.googlecode.com)
	
    svn checkout http://v8.googlecode.com/svn/branches/bleeding_edge/ v8
    svn checkout http://v8.googlecode.com/svn/branches/bleeding_edge/ v8
    svn checkout http://v8.googlecode.com/svn/branches/bleeding_edge/ v8
    svn checkout http://v8.googlecode.com/svn/branches/bleeding_edge/ v8
    svn checkout http://v8.googlecode.com/svn/branches/bleeding_edge/ v8
    cd ..
    
    # Debug builds, keeping the debug source code directory,
    #   in case gdb is needed for symbols.
    cd debug-$branchType/v8/
    scons mode=debug library=shared snapshot=on sample=shell
    cd ../../
fi

if ( [ $compileType = "opt" ] && [ $branchType = "v8" ] ) then
	# 
    # SVN checks out five times, it seems to consistently error out 1 or 2 times.
    # Sample:
    # svn: REPORT request failed on '/svn/!svn/vcc/default'
	# svn: REPORT of '/svn/!svn/vcc/default': 200 OK (http://v8.googlecode.com)
        
	cd ../opt-$branchType
    svn checkout http://v8.googlecode.com/svn/branches/bleeding_edge/ v8
    svn checkout http://v8.googlecode.com/svn/branches/bleeding_edge/ v8
    svn checkout http://v8.googlecode.com/svn/branches/bleeding_edge/ v8
    svn checkout http://v8.googlecode.com/svn/branches/bleeding_edge/ v8
    svn checkout http://v8.googlecode.com/svn/branches/bleeding_edge/ v8
    cd ..
    
    # Opt build.
    cd opt-$branchType/v8/
    scons mode=release library=static snapshot=on sample=shell
    cp shell ../../js-opt-$branchType-intelmac
    cd ../../
    #rm -r opt-$branchType  # do not remove source yet.
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
if ( [ $compileType = "dbg" ] && [ $branchType = "v8" ] ) then
	# v8 engine doesn't allow moving of debug shell.
	cd ~/Desktop/jsfunfuzz-dbg-v8/debug-v8/v8/
	cp ../../jsfunfuzz.js .
  	cp ../../analysis.sh .
	time python -u ~/fuzzing/jsfunfuzz/multi_timed_run.py 1800 ~/Desktop/jsfunfuzz-dbg-v8/debug-v8/v8/shell_g ~/fuzzing/jsfunfuzz/jsfunfuzz.js | tee ~/Desktop/jsfunfuzz-dbg-v8/debug-v8/v8/log-jsfunfuzz
fi

if ( [ $branchType = "moz190" ] ) then
	time python -u ~/fuzzing/jsfunfuzz/multi_timed_run.py 1800 ~/fuzzing/js-known/mozilla-1.9.0/ ~/Desktop/jsfunfuzz-$compileType-$branchType/js-$compileType-$branchType-intelmac ~/fuzzing/jsfunfuzz/jsfunfuzz.js | tee ~/Desktop/jsfunfuzz-$compileType-$branchType/log-jsfunfuzz
fi

if ( [ $branchType = "moz191" ] ) then
	time python -u ~/fuzzing/jsfunfuzz/multi_timed_run.py 1800 ~/fuzzing/js-known/mozilla-1.9.1/ ~/Desktop/jsfunfuzz-$compileType-$branchType/js-$compileType-$branchType-intelmac -j ~/fuzzing/jsfunfuzz/jsfunfuzz.js | tee ~/Desktop/jsfunfuzz-$compileType-$branchType/log-jsfunfuzz
fi

if ( [ $branchType = "mozTrunk" ] ) then
	time python -u ~/fuzzing/jsfunfuzz/multi_timed_run.py 1800 ~/fuzzing/js-known/mozilla-central/ ~/Desktop/jsfunfuzz-$compileType-$branchType/js-$compileType-$branchType-intelmac -j ~/fuzzing/jsfunfuzz/jsfunfuzz.js | tee ~/Desktop/jsfunfuzz-$compileType-$branchType/log-jsfunfuzz
fi

if ( [ $branchType = "tm" ] ) then
	time python -u ~/fuzzing/jsfunfuzz/multi_timed_run.py 1800 ~/fuzzing/js-known/mozilla-central/ ~/Desktop/jsfunfuzz-$compileType-$branchType/js-$compileType-$branchType-intelmac -j ~/fuzzing/jsfunfuzz/jsfunfuzz.js | tee ~/Desktop/jsfunfuzz-$compileType-$branchType/log-jsfunfuzz
fi

echo
date
# change to fuzzing directory.
if ( [ $compileType = "dbg" ] && [ $branchType = "v8" ] ) then
	cd ~/Desktop/jsfunfuzz-dbg-v8/debug-v8/v8/
    ./analysis.sh
    echo
    echo 'PRESENT WORKING DIRECTORY:'
    pwd
    else
	    cd ~/Desktop/jsfunfuzz-$compileType-$branchType
        ./analysis.sh
        echo
        echo 'PRESENT WORKING DIRECTORY:'
        pwd
fi

echo 'REMEMBER TO CHECK TIMED_OUTs, ABNORMALs and CRASHes.'
date
echo

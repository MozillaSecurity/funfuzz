# !/bin/bash
set -eu

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
# The Original Code is autoBisect.
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


# DOC: Run `hg bisect -r`,
# DOC: Give a starting point `hg bisect -g`,
# DOC: Give an ending point `hg bisect -b` first.
testcaseFile=$1
compileType=$2
bad=$3
# DOC: Use "" for things like crashes (they don't send any output to stderr)
requiredOutput=$4

# Copies the existing js source code to a directory on the Desktop.
mkdir -p ~/Desktop/autoBisect-$compileType-tm
cd ~/Desktop/autoBisect-$compileType-tm
mkdir -p $compileType-src
cd $compileType-src
cp -r ~/jaegermonkey/js/src/* .
# DOC: Bash script should fail in Windows (under MozillaBuild).
#      I think they use autoconf-2.13 and I'm not sure how to sniff for it yet.
# DOC: So far, Mac-only support due to the reasons listed below.
# DOC: if bash is in Linux, do autoconf2.13, but if in Mac, do autoconf213.
# DOC: in Linux, test for the exit code for assertions if it is same as 133.
# DOC: differentiates between different assertion messages.
# DOC: does not yet differentiate between crashes at different bad exit codes.
# DOC: -j is turned on by default.
autoconf213


# Compile a js shell depending on command line arguments.
case $compileType in
  # Compile dbg js shells.
  "dbg" )
    mkdir -p dbg-objdir
    cd dbg-objdir
    # For 10.5:
    #../configure --disable-optimize --enable-debug
    # For 10.6:
    CC="gcc-4.2 -arch i386" CXX="g++-4.2 -arch i386" HOST_CC="gcc-4.2" HOST_CXX="g++-4.2" RANLIB=ranlib AR=ar AS=$CC LD=ld STRIP="strip -x -S" CROSS_COMPILE=1 sh ../configure --target=i386-apple-darwin8.0.0 --disable-optimize --enable-debug --enable-methodjit
    make -j2
#    if make -j2; then
# Note: this doesn't yet work!
#       # Miscellaneous problems, such as build problems, should be skipped.
#       dbgCompileExitCode=$?
#       if ([ "$dbgCompileExitCode" != 0 ]); then
#         cd ~/tracemonkey/
#         echo "SKIPPED changeset: hg bisect -s"
#         hg bisect -s;
#         echo -n "You are now currently in hg revision: "
#         hg identify -n
#         rm -rf ~/Desktop/autoBisect-$compileType-tm/
#         exit 0;
#      fi
#    fi
    cp js ../../js-dbg-tm
    cd ../../
    ;;
  
  # Compile opt js shells.
  "opt" )
    mkdir -p opt-objdir
    cd opt-objdir
    # For 10.5:
    #../configure --enable-optimize --disable-debug
    # For 10.6:
    CC="gcc-4.2 -arch i386" CXX="g++-4.2 -arch i386" HOST_CC="gcc-4.2" HOST_CXX="g++-4.2" RANLIB=ranlib AR=ar AS=$CC LD=ld STRIP="strip -x -S" CROSS_COMPILE=1 sh ../configure --target=i386-apple-darwin8.0.0 --enable-optimize --disable-debug --enable-methodjit
    make -j2
#    if make -j2; then
# Note: this doesn't yet work!
#       # Miscellaneous problems, such as build problems, should be skipped.
#       optCompileExitCode=$?
#       if ([ "$optCompileExitCode" != 0 ]); then
#         cd ~/tracemonkey/
#         echo "SKIPPED changeset: hg bisect -s"
#         hg bisect -s;
#         echo -n "You are now currently in hg revision: "
#         hg identify -n
#         rm -rf ~/Desktop/autoBisect-$compileType-tm/
#         exit 0;
#      fi
#    fi
    cp js ../../js-opt-tm
    cd ../../
    ;;
  
  # Stop and exit if wrong arguments are given.
  *     )
    echo
    echo "usage: ./autoBisect.sh <locationOfTestcase> [dbg|opt] [bug|wfm] output"
    echo "  (use \"\" as output for crashes)"
    echo
    cd ~/Desktop/
    rm -rf autoBisect-$compileType-tm
    exit 0;;
esac

# Run the testcase on the compiled js binary.
if ./js-$compileType-tm -mj $testcaseFile > tempResult 2>&1; then
  exitCode=$?
  echo -n "The exit code is: "
  echo $exitCode
else
  exitCode=$?
  cat tempResult
  echo -n "The exit code is: "
  echo $exitCode
fi

# Switch to hg repository directory.
cd ~/jaegermonkey/

# If exact assertion failure message is found (debug shells only),
#   return a bad exit code.
# Exit code 133 is the number for Trace/BFT trap on Mac Leopard
#   (exit code for Mac assertions)
# More information on exit codes:
# http://tldp.org/LDP/abs/html/exitcodes.html
if ([ "$compileType" = dbg ] && [ "$exitCode" != 0 ] && [ "$exitCode" = 133 ]); then

  # Look for the required assertion message which was piped into a temp file.
  if grep -q "$requiredOutput" ~/Desktop/autoBisect-$compileType-tm/tempResult; then
    if [ "$bad" = bug ]; then
      echo "BAD changeset: hg bisect -b"
      hg bisect -b;
    fi
    if [ "$bad" = wfm ]; then
      echo "GOOD changeset: hg bisect -g"
      hg bisect -g;
    fi
    echo -n "You are now currently in hg revision: "
    hg identify -n
    rm -rf ~/Desktop/autoBisect-$compileType-tm/
    exit 0;
  fi

  # If another assertion failure message is found, abort hg bisect.
  echo "Assertion morphed! Skipping changeset ... "
  echo "SKIPPED changeset: hg bisect -s"
  hg bisect -s;
  echo -n "You are now currently in hg revision: "
  hg identify -n
  rm -rf ~/Desktop/autoBisect-$compileType-tm/
  exit 0;
fi

# Only for bad changesets.
if ([ "$exitCode" = 1 ] || [ 129 -le "$exitCode" -a "$exitCode" -le 159 ]); then
  if [ "$bad" = bug ]; then
    echo "BAD changeset: hg bisect -b"
    hg bisect -b;
  fi
  if [ "$bad" = wfm ]; then
    echo "GOOD changeset: hg bisect -g"
    hg bisect -g;
  fi
  echo -n "You are now currently in hg revision: "
  hg identify -n
  rm -rf ~/Desktop/autoBisect-$compileType-tm/
  exit 0;
fi

# If exit code is 0, it is a good changeset.
if ([ "$exitCode" = 0 ] || [ 3 -le "$exitCode" -a "$exitCode" -le 6 ]); then
  if [ "$bad" = bug ]; then
    echo "GOOD changeset: hg bisect -g"
    hg bisect -g;
  fi
  if [ "$bad" = wfm ]; then
    echo "BAD changeset: hg bisect -b"
    hg bisect -b;
  fi
  echo -n "You are now currently in hg revision: "
  hg identify -n
  rm -rf ~/Desktop/autoBisect-$compileType-tm/
  exit 0;
fi

# Miscellaneous problems should be skipped.
# echo "SKIPPED changeset: hg bisect -s"
# hg bisect -s;
# echo -n "You are now currently in hg revision: "
# hg identify -n
# rm -rf ~/Desktop/autoBisect-$compileType-tm/
# exit 0;

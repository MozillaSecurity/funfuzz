set -eu
# !/bin/bash
# Run |hg bisect -r|,
# give a starting point |hg bisect -g|,
# give an ending point |hg bisect -b| first.
compileType=$1
branchType=$2
testcaseFile=$3
# To bisect for WFM, use 1 for good and 0 for bad.
# To bisect for bugs, use 0 for good and 1 for bad.
bad=$4
requiredOutput=$5

cd ~/fuzzing/jsfunfuzz/
bash compileNoFuzz-jsfunfuzz.sh $compileType $branchType
cd ~/Desktop/jsfunfuzz-$compileType-$branchType/
if ./js-$compileType-$branchType-intelmac -j $testcaseFile > tempResult 2>&1; then
  exitCode=$?
  echo $exitCode
  echo SUCCESS
else
  exitCode=$?
  cat tempResult
  echo $exitCode
  echo FAILURE
fi
echo -n "exitCode is: "
echo $exitCode
cd ~/tracemonkey/

# If exact assertion failure message is found (debug shells only), return a bad exit code.
# If another assertion failure message is found, abort hg bisect.
# Exit code 133 is the number for Trace/BFT trap on Mac Leopard.
if ( [ "$compileType" = dbg ] && [ "$exitCode" != 0 ] && [ "$exitCode" = 133 ] ); then

  if grep -q "$requiredOutput" ~/Desktop/jsfunfuzz-$compileType-$branchType/tempResult; then
    # The next two lines are the equivalent of "hg bisect -$bad".
    if [ "$bad" = 1 ]; then
      echo "hg bisect -b"
      hg bisect -b;
    fi
    if [ "$bad" = 0 ]; then
      echo "hg bisect -g"
      hg bisect -g;
    fi
    rm -rf ~/Desktop/jsfunfuzz-$compileType-$branchType/
    exit 0;
  fi

  rm -rf ~/Desktop/jsfunfuzz-$compileType-$branchType/;
fi

# Only for bad changesets.
if [ 129 -le "$exitCode" -a "$exitCode" -le 159 ]; then
  # The next two sections are the equivalent of "hg bisect -$bad".
  if [ "$bad" = 1 ]; then
    echo "hg bisect -b"
    hg bisect -b;
  fi
  if [ "$bad" = 0 ]; then
    echo "hg bisect -g"
    hg bisect -g;
  fi
  rm -rf ~/Desktop/jsfunfuzz-$compileType-$branchType/
  exit 0;
fi

# If exit code is 0, it is a good changeset.
if [ $exitCode = "0" ]; then
  # The next two sections are the equivalent of "hg bisect -$good".
  if [ "$bad" = 1 ]; then
    echo "hg bisect -g"
    hg bisect -g;
  fi
  if [ "$bad" = 0 ]; then
    echo "hg bisect -b"
    hg bisect -b;
  fi
  rm -rf ~/Desktop/jsfunfuzz-$compileType-$branchType/
  exit 0;
fi


# After finding the required changeset, remember to |hg bisect -r| again.
#if exitCode 127 or 1, abort! (exit 0)
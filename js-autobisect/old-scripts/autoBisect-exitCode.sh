# !/bin/bash
# Run |hg bisect -r|,
# give a starting point |hg bisect -g|,
# give an ending point |hg bisect -b| first.
compileType=$1
branchType=$2
testcaseFile=$3
requiredOutput=$4

cd ~/fuzzing/jsfunfuzz/
bash compileNoFuzz-jsfunfuzz.sh $compileType $branchType
cd ~/Desktop/jsfunfuzz-$compileType-$branchType/
./js-$compileType-$branchType-intelmac -j $testcaseFile > tempResult 2>&1
exitCode=$?

# To bisect for WFM, use 1 for good and 0 for bad.
# To bisect for bugs, use 0 for good and 1 for bad.
$good=1
$bad=0

# If exact assertion failure message is found (debug shells only), return a bad exit code.
# If another assertion failure message is found, abort hg bisect.
# Exit code 133 is the number for Trace/BFT trap on Mac Leopard.
if ( [ $compileType = "dbg" ] && [ $exitCode != "0" ] && [ $exitCode == "133" ] ) then

if grep -q "$requiredOutput" tempResult; then
rm -rf ~/Desktop/jsfunfuzz-$compileType-$branchType/
exit $bad
fi

rm -rf ~/Desktop/jsfunfuzz-$compileType-$branchType/
exit 127;
fi

# Only for bad changesets.
if [ $exitCode != "0" ] then
rm -rf ~/Desktop/jsfunfuzz-$compileType-$branchType/
exit $bad
fi

# If exit code is 0, it is a good changeset.
if [ $exitCode == "0" ] then
rm -rf ~/Desktop/jsfunfuzz-$compileType-$branchType/
exit $good
fi

# After finding the required changeset, remember to |hg bisect -r| again.
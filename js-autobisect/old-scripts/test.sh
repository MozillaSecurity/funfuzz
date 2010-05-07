# !/bin/bash
# Run |hg bisect -r| first.
# Give a starting point and an ending point first.
compileType=$1
branchType=$2
testcaseFile=$3
requiredOutput=$4

cd ~/fuzzing/jsfunfuzz/
bash compileNoFuzz-jsfunfuzz.sh $compileType $branchType
cd ~/Desktop/jsfunfuzz-$compileType-$branchType/
bash -c "./js-$compileType-$branchType-intelmac -j $testcaseFile" >tempResult 2>&1

# To bisect for WFM, use good then bad.
# To bisect for existing bugs, use bad then good.
if grep -q '$requiredOutput' tempResult
#if ( [ $? != "0" ] ) then
  then
    result=good
  else
    result=bad
  fi
echo this revision is $result
cd ~/tracemonkey/
hg bisect --$result
#rm -rf ~/Desktop/jsfunfuzz-$compileType-$branchType/

# After finding the required changeset, remember to |hg bisect -r| again.
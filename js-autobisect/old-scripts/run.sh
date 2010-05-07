#! /bin/bash
set -eu

cd ~/tracemonkey/
#cd ~/jaegermonkey/ # REPLACEME
# DOC: This wipes out all local hg changes on the ~/tracemonkey/ directory!
hg up -C default
hg bisect -r
hg bisect -g 41288 # REPLACEME, verify this is a "good" changeset manually.
hg bisect -b 41535 # REPLACEME, verify this is a "bad" changeset manually.

# Enter the number of iterations estimated by hg,
# after the "good" and "bad" changesets are entered.
echo
echo -n "Please key in hg's number of estimated tests: "
read LIMIT
echo "Note that one more test will be run to double check."
echo

# Sometimes the estimation done by hg is not entirely accurate. Sometimes one
# more test round is needed. It does not hurt to have one more test even if
# it is not needed.
for ((a=0; a <= LIMIT ; a++))  # Double parentheses, and "LIMIT" with no "$".
do
bash ~/Desktop/autoBisect.sh ~/Desktop/2interesting/563210.js dbg bug "ssertion fail" # REPLACEME
#bash ~/Desktop/autoBisect-jm-no-m-with-j.sh ~/Desktop/2interesting/w35-reduced.js dbg bug "ssertion failure"
#bash ~/Desktop/autoBisect.sh ~/Desktop/2interesting/563127.js opt bug "" # REPLACEME
#bash ~/Desktop/autoBisect-notExitCode.sh ~/Desktop/2interesting/543100.js opt bug "" # REPLACEME
done

hg bisect -r

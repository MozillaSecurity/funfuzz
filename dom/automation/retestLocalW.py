#!/usr/bin/env python

import os
import re
import subprocess
import sys
import time

build = sys.argv[1]
fullu = os.path.expanduser("~")
dominteresting_py = os.path.join(fullu, "funfuzz", "dom", "automation", "domInteresting.py")


def timestamp():
    return str(int(time.time()))


for wn in os.listdir(fullu):
    if wn.startswith("wtmp"):
        fullwn = os.path.join(fullu, wn)
        for filename in os.listdir(fullwn):
            match = re.match(r"(q\d+)-splice-reduced\..*", filename)
            if match:
                fullFilename = os.path.join(fullwn, filename)
                dicall = [sys.executable, dominteresting_py, "--background", "--submit", build, fullFilename]
                outfn = os.path.join(fullwn, match.group(1) + "-retest-out-" + timestamp() + ".txt")
                with open(outfn, "w") as out:
                    if subprocess.call(dicall, stdout=out, stderr=subprocess.STDOUT):
                        print fullFilename
                        print outfn


# pbpaste | xargs open -a "Sublime Text"

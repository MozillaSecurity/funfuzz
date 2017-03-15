#!/usr/bin/env python

from __future__ import absolute_import

import json
import os
import re


def fuzzManagerKnownBugs():
    bugs = []
    sk = os.path.expanduser("~/sigcache/")
    for fn in os.listdir(sk):
        if fn.endswith(".metadata"):
            with open(os.path.join(sk, fn)) as f:
                metadata = json.load(f)
                bug = metadata.get("bug__id")
                if bug is not None:
                    bug = bug.strip()
                    if bug != "":
                        bugs.append(bug)
    return bugs


def bugNumbersIn(s):
    return [match.group(1) for match in re.finditer(r"[bB]ug (\d+)", s)]


assert bugNumbersIn("Bug 123, bug 456") == ["123", "456"]
assert bugNumbersIn("") == []


def exportSignatures(validSymptom, fmkb, files):
    exports = []
    for fn in files:
        lastComment = ""
        knownToFuzzManager = False
        for line in open(fn):
            line = line.strip()
            if line == "":
                pass
            elif line.startswith("#"):
                lastComment = line
                knownToFuzzManager = False
                for bug in fmkb:
                    if bug in line:
                        knownToFuzzManager = True
                        print "Skipping bug known to fuzzmanager: " + line
                        print
                        break
            elif validSymptom(line):
                if not knownToFuzzManager:
                    bugs = bugNumbersIn(lastComment)
                    for bug in bugs:
                        exports.append({'symptom': line, 'bug': bug, 'note': lastComment})
                    if len(bugs) == 0:
                        print "No bug number: "
                        print lastComment
                        print line
                        print
    return exports


def validAssertion(line):
    # We only want fatal assertions
    return line.startswith("Assertion failure") or line.startswith(":")


def validCrash(line):
    # Skip crashes with [TMR], [EXPLOITABLE], or stack indices
    return not line.startswith("[") and not line.strip()[0].isdigit()


def main():
    fmkb = fuzzManagerKnownBugs()

    print
    print "### FATAL ASSERTIONS ###"
    print
    print json.dumps(exportSignatures(validAssertion, fmkb,
        [
            os.path.expanduser("~/funfuzz/known/mozilla-central/assertions.txt"),
            os.path.expanduser("~/funfuzz-private/known/mozilla-central/assertions.txt")
        ]), indent=4)

    print
    print "### CRASHES ###"
    print
    print json.dumps(exportSignatures(validCrash, fmkb,
        [
            os.path.expanduser("~/funfuzz/known/mozilla-central/crashes.txt"),
            os.path.expanduser("~/funfuzz-private/known/mozilla-central/crashes.txt")
        ]), indent=4)


if __name__ == "__main__":
    main()

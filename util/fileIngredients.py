#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import with_statement

import re

def fileContains(f, s, isRegex):
    if isRegex:
        return fileContainsRegex(f, re.compile(s, re.MULTILINE))
    else:
        return fileContainsStr(f, s), s


def fileContainsStr(f, s):
    found = False
    with open(f, 'rb') as g:
        for line in g:
            if line.find(s) != -1:
                print line.rstrip()
                found = True
    return found

def fileContainsRegex(f, regex):
    # e.g. ~/fuzzing/lithium/lithium.py crashesat --timeout=30
    #       --regex '^#0\s*0x.* in\s*.*(?:\n|\r\n?)#1\s*' ./js --ion -n 735957.js
    # Note that putting "^" and "$" together is unlikely to work.
    matchedStr = ''
    found = False
    with open(f, 'rb') as g:
        foundRegex = regex.search(g.read())
        if foundRegex:
            matchedStr = foundRegex.group()
            print matchedStr
            found = True
    return found, matchedStr

#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import with_statement

def firstLine(s):
    '''Returns the first line of any series of text with / without line breaks.'''
    return s.split('\n')[0]

def fuzzDice(filename):
    '''Returns the lines of the file, except for the one line containing DICE'''
    before = []
    after = []
    with open(filename, 'rb') as f:
        for line in f:
            if line.find("DICE") != -1:
                break
            before.append(line)
        for line in f:
            after.append(line)
    return [before, after]

def fuzzSplice(filename):
    '''Returns the lines of a file, minus the ones between the two lines containing SPLICE'''
    before = []
    after = []
    with open(filename, 'rb') as f:
        for line in f:
            before.append(line)
            if line.find("SPLICE") != -1:
                break
        for line in f:
            if line.find("SPLICE") != -1:
                after.append(line)
                break
        for line in f:
            after.append(line)
    return [before, after]

def linesWith(lines, searchFor):
    '''Returns the lines from an array that contain a given string'''
    matchingLines = []
    for line in lines:
        if line.find(searchFor) != -1:
            matchingLines.append(line)
    return matchingLines

def writeLinesToFile(lines, filename):
    '''Writes lines to a given filename.'''
    with open(filename, 'wb') as f:
        f.writelines(lines)

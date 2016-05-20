#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# This file scans the revsets in ignoreAndEarliestWorkingLists and looks for overlaps.
#
# Usage: python findCsetsIntersection.py -R ~/trees/mozilla-central/
#
# (first go to knownBrokenEarliestWorking.py and comment out configuration-specific ignore ranges,
# this file does not yet support those.)

import os
import sys
from optparse import OptionParser

import knownBrokenEarliestWorking as kbew
path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
import subprocesses as sps


def parseOptions():
    parser = OptionParser()
    parser.add_option('-R', '--repo', dest='rDir',
                      help='Sets the repository to analyze..')
    options, _args = parser.parse_args()
    assert options.rDir is not None
    assert os.path.isdir(sps.normExpUserPath(options.rDir))
    return options


def countCsets(revset, rdir):
    """Count the number of changesets in the revsets by outputting ones and counting them."""
    listCmd = ['hg', 'log', '-r', revset, '--template=1']
    rangeIntersectionOnes = sps.captureStdout(listCmd, currWorkingDir=rdir)
    assert rangeIntersectionOnes[1] == 0
    return len(rangeIntersectionOnes[0])


def main():
    options = parseOptions()
    repoDir = options.rDir
    brokenRanges = kbew.knownBrokenRanges(options)

    cnt = 0
    for i in range(0, len(brokenRanges)):
        print 'Analyzing revset: ' + brokenRanges[i] + \
            ' which matches ' + str(countCsets(brokenRanges[i], repoDir)) + ' changesets'
        for j in range(i + 1, len(brokenRanges)):
            cnt += 1
            print 'Number ' + str(cnt) + ': Compared against revset: ' + brokenRanges[j]
            overlap = countCsets(brokenRanges[i] + ' and ' + brokenRanges[j], repoDir)
            if overlap > 0:
                print 'Number of overlapping changesets: ' + str(overlap)
        cnt = 0


if __name__ == '__main__':
    main()

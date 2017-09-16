#!/usr/bin/env python
# coding=utf-8
# pylint: disable=invalid-name,missing-docstring
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# This file scans the revsets in ignoreAndEarliestWorkingLists and looks for overlaps.
#
# Usage: python findCsetsIntersection.py -R ~/trees/mozilla-central/
#
# (first go to knownBrokenEarliestWorking.py and comment out configuration-specific ignore ranges,
# this file does not yet support those.)

from __future__ import absolute_import, print_function

import os
from optparse import OptionParser  # pylint: disable=deprecated-module

from . import knownBrokenEarliestWorking as kbew
from ..util import subprocesses as sps


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
        print("Analyzing revset: %s which matches %s changesets" % (
            brokenRanges[i], countCsets(brokenRanges[i], repoDir)))
        for j in range(i + 1, len(brokenRanges)):
            cnt += 1
            print("Number %s: Compared against revset: %s" % (cnt, brokenRanges[j]))
            overlap = countCsets(brokenRanges[i] + ' and ' + brokenRanges[j], repoDir)
            if overlap:
                print("Number of overlapping changesets: %s" % (overlap,))
        cnt = 0


if __name__ == '__main__':
    main()

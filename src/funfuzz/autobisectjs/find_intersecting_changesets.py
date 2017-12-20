# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""This file scans the revsets in ignoreAndEarliestWorkingLists and looks for overlaps.

Usage: python -m funfuzz.autobisectjs.find_intersecting_changesets -R ~/trees/mozilla-central/

(first go to known_broken_earliest_working and comment out configuration-specific ignore ranges,
this file does not yet support those.)"""

from __future__ import absolute_import, print_function

import os
from optparse import OptionParser  # pylint: disable=deprecated-module

from . import known_broken_earliest_working as kbew
from ..util import subprocesses as sps


def parse_options():  # pylint: disable=missing-docstring,missing-return-doc,missing-return-type-doc
    parser = OptionParser()
    parser.add_option('-R', '--repo', dest='rDir',
                      help='Sets the repository to analyze..')
    options, _args = parser.parse_args()
    assert options.rDir is not None
    assert os.path.isdir(sps.normExpUserPath(options.rDir))
    return options


def count_csets(revset, rdir):  # pylint: disable=missing-param-doc,missing-return-doc,missing-return-type-doc
    # pylint: disable=missing-type-doc
    """Count the number of changesets in the revsets by outputting ones and counting them."""
    cmd = ['hg', 'log', '-r', revset, '--template=1']
    range_intersection_ones = sps.captureStdout(cmd, currWorkingDir=rdir)
    assert range_intersection_ones[1] == 0
    return len(range_intersection_ones[0])


def main():  # pylint: disable=missing-docstring
    options = parse_options()
    repo_dir = options.rDir
    broken_ranges = kbew.known_broken_ranges(options)

    cnt = 0
    for i in range(0, len(broken_ranges)):  # pylint: disable=consider-using-enumerate
        print("Analyzing revset: %s which matches %s changesets" % (
            broken_ranges[i], count_csets(broken_ranges[i], repo_dir)))
        for j in range(i + 1, len(broken_ranges)):
            cnt += 1
            print("Number %s: Compared against revset: %s" % (cnt, broken_ranges[j]))
            overlap = count_csets(broken_ranges[i] + ' and ' + broken_ranges[j], repo_dir)
            if overlap:
                print("Number of overlapping changesets: %s" % (overlap,))
        cnt = 0


if __name__ == '__main__':
    main()

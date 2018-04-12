# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Functions dealing with files and their contents.
"""

from __future__ import absolute_import, print_function


def fuzzSplice(filename):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc,missing-return-type-doc
    # pylint: disable=missing-type-doc
    """Return the lines of a file, minus the ones between the two lines containing SPLICE."""
    before = []
    after = []
    with open(filename, "r") as f:
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


def linesWith(lines, search_for):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Return the lines from an array that contain a given string."""
    matched = []
    for line in lines:
        if line.find(search_for) != -1:
            matched.append(line)
    return matched


def linesStartingWith(lines, search_for):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Return the lines from an array that start with a given string."""
    matched = []
    for line in lines:
        if line.startswith(search_for):
            matched.append(line)
    return matched


def truncateMid(a, limit_each_side, insert_if_truncated):  # pylint: disable=invalid-name,missing-param-doc
    # pylint: disable=missing-return-doc,missing-return-type-doc,missing-type-doc
    """Return a list with the middle portion removed, if it has more than limit_each_side*2 items."""
    if len(a) <= limit_each_side + limit_each_side:
        return a
    return a[0:limit_each_side] + insert_if_truncated + a[-limit_each_side:]

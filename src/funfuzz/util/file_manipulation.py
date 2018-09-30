# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Functions dealing with files and their contents.
"""

import io


def amiss(log_prefix):  # pylint: disable=missing-param-doc,missing-return-doc,missing-return-type-doc,missing-type-doc
    """Look for "szone_error" (Tiger), "malloc_error_break" (Leopard), "MallocHelp" (?)
    which are signs of malloc being unhappy (double free, out-of-memory, etc).
    """
    found_something = False
    err_log = (log_prefix.parent / f"{log_prefix.stem}-err").with_suffix(".txt")
    with io.open(str(err_log), "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip("\x07").rstrip("\n")
            if (line.find("szone_error") != -1 or
                    line.find("malloc_error_break") != -1 or
                    line.find("MallocHelp") != -1):
                print()
                print(line)
                found_something = True
                break  # Don't flood the log with repeated malloc failures

    return found_something


def fuzzSplice(filename):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc,missing-return-type-doc
    # pylint: disable=missing-type-doc
    """Return the lines of a file, minus the ones between the two lines containing SPLICE."""
    before = []
    after = []
    with io.open(str(filename), "r", encoding="utf-8", errors="replace") as f:
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

# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Look for "szone_error" (Tiger), "malloc_error_break" (Leopard), "MallocHelp" (?)
which are signs of malloc being unhappy (double free, out-of-memory, etc).
"""

from __future__ import absolute_import, print_function

PLINE = ""
PPLINE = ""


def amiss(log_prefix):  # pylint: disable=missing-docstring,missing-return-doc,missing-return-type-doc
    found_something = False
    global PLINE, PPLINE  # pylint: disable=global-statement

    PLINE = ""
    PPLINE = ""

    with open(log_prefix + "-err.txt") as f:
        for line in f:
            if scanLine(line):
                found_something = True
                break  # Don't flood the log with repeated malloc failures

    return found_something


def scanLine(line):  # pylint: disable=inconsistent-return-statements,invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    global PPLINE, PLINE  # pylint: disable=global-statement

    line = line.strip("\x07").rstrip("\n")

    if (line.find("szone_error") != -1 or
            line.find("malloc_error_break") != -1 or
            line.find("MallocHelp") != -1):
        if PLINE.find("can't allocate region") == -1:
            print()
            print(PPLINE)
            print(PLINE)
            print(line)
            return True

    PPLINE = PLINE
    PLINE = line

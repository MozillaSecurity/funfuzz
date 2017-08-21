#!/usr/bin/env python
# coding=utf-8
# pylint: disable=global-statement,invalid-name,missing-docstring
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import absolute_import, print_function

# Look for "szone_error" (Tiger), "malloc_error_break" (Leopard), "MallocHelp" (?)
# which are signs of malloc being unhappy (double free, out-of-memory, etc).

pline = ""
ppline = ""


def amiss(logPrefix):
    foundSomething = False
    global pline, ppline

    pline = ""
    ppline = ""

    with open(logPrefix + "-err.txt") as f:
        for line in f:
            if scanLine(line):
                foundSomething = True
                break  # Don't flood the log with repeated malloc failures

    return foundSomething


def scanLine(line):
    global ppline, pline

    line = line.strip("\x07").rstrip("\n")

    if (line.find("szone_error") != -1 or
            line.find("malloc_error_break") != -1 or
            line.find("MallocHelp") != -1):
        if pline.find("can't allocate region") == -1:
            print()
            print(ppline)
            print(pline)
            print(line)
            return True

    ppline = pline
    pline = line

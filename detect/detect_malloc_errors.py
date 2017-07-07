#!/usr/bin/env python

from __future__ import absolute_import

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
            print ""
            print ppline
            print pline
            print line
            return True

    ppline = pline
    pline = line

#!/usr/bin/env python

# Look for "szone_error" (Tiger), "malloc_error_break" (Leopard), "MallocHelp" (?)
# which are signs of malloc being unhappy (double free, out-of-memory, etc).

# This has only been tested on Tiger.

def amiss(logPrefix):
    foundSomething = False

    currentFile = file(logPrefix + "-err", "r")
    
    pline = ""
    ppline = ""

    for line in currentFile:
        line = line.strip("\x07").rstrip("\n")
        
        if (-1 != line.find("szone_error")
         or -1 != line.find("malloc_error_break")
         or -1 != line.find("MallocHelp")):
            print ""
            print ppline
            print pline
            print line
            foundSomething = True
            break # Don't flood the log with repeated malloc failures

        ppline = pline
        pline = line

    currentFile.close()
    
    return foundSomething

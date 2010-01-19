#!/usr/bin/env python

import sys
import xml.dom.minidom

def prettyStack(error):
    r = ""
    stack = error.getElementsByTagName("stack")[0]
    for frame in stack.childNodes:
        if frame.nodeType == frame.ELEMENT_NODE:
            objs = frame.getElementsByTagName("obj")
            obj = objs[0].firstChild.data if len(objs) > 0 else "noobj"
            fns = frame.getElementsByTagName("fn")
            fn = fns[0].firstChild.data if len(fns) > 0 else "unknown"
            files = frame.getElementsByTagName("file")
            lines = frame.getElementsByTagName("line")
            file = None
            r += fn + " ("
            if len(files) > 0:
                file = files[0].firstChild.data
                if len(lines) > 0:
                    file += ":" + lines[0].firstChild.data
                r += file
            else:
                r += "in " + obj
            r += ")\n"
    return r

def amiss(fn, ignoreLeaks):
    a = False

    try:
        dom = xml.dom.minidom.parse(fn)
    except xml.parsers.expat.ExpatError, e:
        print "Error parsing the valgrind log: " + str(e)
        return False

    for error in dom.getElementsByTagName("error"):
        kind = error.getElementsByTagName("kind")[0].firstChild.data
        if kind == "Leak_PossiblyLost":
            continue # many false positives, or system library leaks, or something.
        if kind == "Leak_DefinitelyLost" and ignoreLeaks:
            continue # this is the easiest way to work around bug 102229. more sophisticated would be to scan for DNS leaks first, or use the known-leak list.

        # Apparently some Valgrind errors (e.g. leaks) give "xwhat" while others (e.g. UMR) give "what".  xwtf.
        if len(error.getElementsByTagName("xwhat")) > 0:
            print error.getElementsByTagName("xwhat")[0].getElementsByTagName("text")[0].firstChild.data
        elif len(error.getElementsByTagName("what")) > 0:
            print error.getElementsByTagName("what")[0].firstChild.data
        print prettyStack(error)

        a = True

    dom.unlink()
    return a

if __name__ == '__main__':
    print amiss(sys.argv[1], True)

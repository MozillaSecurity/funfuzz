#!/usr/bin/env python

import sys
import xml.dom.minidom

(BLAME_MOZILLA, BLAME_DONT_CARE, BLAME_MAC_LIBRARIES, BLAME_UNKNOWN) = range(4)


def blame(error):
    stack = error.getElementsByTagName("stack")[0]
    for frame in stack.childNodes:
        if frame.nodeType == frame.ELEMENT_NODE:
            fns = frame.getElementsByTagName("fn")
            if len(fns) > 0:
                fn = fns[0].firstChild.data
                if fn == "__static_initialization_and_destruction_0(int, int)":
                    return BLAME_DONT_CARE # XXX TEMPORARY (should try firefox debug or objdump/asm)
            objs = frame.getElementsByTagName("obj")
            if len(objs) > 0:
                obj = objs[0].firstChild.data
                if obj.find("valgrind") != -1:
                    pass
                elif obj.find("nssutil") != -1:
                    return BLAME_DONT_CARE # NSS
                elif obj.find("Darwin_SINGLE_SHLIB") != -1:
                    return BLAME_DONT_CARE # NSS
                elif obj.find("central/opt-obj") != -1:
                    return BLAME_MOZILLA
                elif obj == "./js":
                    return BLAME_MOZILLA
                elif obj.find("tracemonkey") != -1:
                    return BLAME_MOZILLA
                elif obj.find("/System/Library/") != -1:
                    return BLAME_MAC_LIBRARIES
                elif obj.find("/usr/lib/") != -1:
                    return BLAME_MAC_LIBRARIES
    return BLAME_UNKNOWN

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

def amiss(fn):
    a = False
    try:
        dom = xml.dom.minidom.parse(fn)
    except xml.parsers.expat.ExpatError, e:
        print "Error parsing the valgrind log: " + str(e)
        return False
    for error in dom.getElementsByTagName("error"):
        kind = error.getElementsByTagName("kind")[0].firstChild.data
        if kind == "Leak_PossiblyLost":
            continue
        b = blame(error)
        if b == BLAME_MOZILLA or b == BLAME_UNKNOWN:
            print "Blame: " + str(b)
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
    print amiss(sys.argv[1])

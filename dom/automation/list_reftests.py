#!/usr/bin/env python

# Based on js/src/tests/manifest.py

import os, re
from subprocess import *


def parse(filename, add_result_callback):
    comment_re = re.compile(r'#.*') # this is wrong, because URLs are allowed to have #, but that works just fine for the fuzzer
    reldir = os.path.dirname(filename)

    with open(filename) as f:
        for line in f:
            sline = comment_re.sub('', line)
            parts = sline.split()
            if len(parts) == 0:
                # line is empty or just a comment, skip
                pass
            elif parts[0] == 'url-prefix':
                pass
            else:
                pos = 0
                while pos < len(parts):
                    # http://hg.mozilla.org/mozilla-central/file/866777368827/layout/tools/reftest/print-manifest-dirs.py#l42
                    K = ['fails', 'needs-focus', 'random', 'skip', 'asserts', 'slow', 'require-or', 'silentfail', 'pref', 'test-pref', 'ref-pref', 'fuzzy', 'default-preferences']
                    part = parts[pos]
                    if any([part.startswith(k) for k in K]):
                        # fails, fails-if(...), asserts(3)
                        #print "Skipping: " + part
                        pos += 1
                        pass
                    elif part == 'include':
                        pos += 1
                        parse(os.path.normpath(os.path.join(reldir, parts[pos])), add_result_callback)
                        break
                    elif part.startswith("HTTP"):
                        pos += 1
                        pass
                    elif part in ["==", "!=", "load"]:
                        pos += 1
                        while pos < len(parts):
                            part = parts[pos]
                            if not part.startswith("data:") and not part.startswith("javascript:") and not part.startswith("about:") and not part.startswith("view-source:"):
                                add_result_callback(os.path.join(reldir, parts[pos]))
                            pos += 1
                        break
                    elif part == "script":
                        break
                    else:
                        print 'warning: in %s unrecognized manifest line element "%s"' % (filename, parts[pos])
                        pos += 1

testfiles = set()

def add_result(r):
    if not ("pngsuite" in r or "351236" in r or "432561" in r or "wrapper.html" in r or "xul" in r or "xbl" in r or r.endswith(".sjs")):
        if r not in testfiles:
            assert r.startswith(sourcetree)
            if not os.path.exists(r.split("?")[0]):
                raise Exception("Missing test: " + r.split("?")[0])
            testfiles.add(r.split("?")[0])

sourcetree = os.path.expanduser("~/trees/mozilla-central/") # XXX assumption alert!

parse(os.path.join(sourcetree, "layout/reftests/reftest.list"), add_result)
parse(os.path.join(sourcetree, "testing/crashtest/crashtests.list"), add_result)

for testfile in testfiles:
    print testfile[len(sourcetree):].lstrip("\\/")

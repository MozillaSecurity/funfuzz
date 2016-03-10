import os
import sys


THIS_SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

fuzzManagerPath = os.path.abspath(os.path.join(THIS_SCRIPT_DIRECTORY, os.pardir, os.pardir, 'FuzzManager'))
if not os.path.exists(fuzzManagerPath):
    print "Please check out Lithium and FuzzManager side-by-side with funfuzz. Links in https://github.com/MozillaSecurity/funfuzz/#setup"
    sys.exit(2)
sys.path.append(fuzzManagerPath)
from Collector.Collector import Collector


def createCollector(tool):
    assert tool == "DOMFuzz" or tool == "jsfunfuzz"
    cacheDir = os.path.normpath(os.path.expanduser(os.path.join("~", "sigcache")))
    try:
        os.mkdir(cacheDir)
    except OSError:
        pass  # cacheDir already exists
    collector = Collector(sigCacheDir=cacheDir, tool=tool)
    return collector


def printCrashInfo(crashInfo):
    if crashInfo.createShortSignature() != "No crash detected":
        print
        print "crashInfo:"
        print "  Short Signature: " + crashInfo.createShortSignature()
        print "  Class name: " + crashInfo.__class__.__name__   # "NoCrashInfo", etc
        print "  Stack trace: " + repr(crashInfo.backtrace)
        print


def printMatchingSignature(match):
    print "Matches signature in FuzzManager:"
    print "  Signature description: " + match[1].get('shortDescription')
    print "  Signature file: " + match[0]
    print

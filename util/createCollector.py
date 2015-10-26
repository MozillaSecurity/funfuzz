import os
import platform
import sys

THIS_SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

fuzzManagerPath = os.path.abspath(os.path.join(THIS_SCRIPT_DIRECTORY, os.pardir, os.pardir, 'FuzzManager'))
if not os.path.exists(fuzzManagerPath):
    print "Please check out Lithium and FuzzManager side-by-side with funfuzz. Links in https://github.com/MozillaSecurity/funfuzz/#setup"
    sys.exit(2)
sys.path.append(fuzzManagerPath)
from Collector.Collector import Collector
from FTB.ProgramConfiguration import ProgramConfiguration


def createCollector(tool):
    assert tool == "DOMFuzz" or tool == "jsfunfuzz"

    # XXX directory name for other machines?
    sigCacheDir = os.path.join(os.path.expanduser("~"), "sigcache")

    collector = Collector(tool=tool, sigCacheDir=sigCacheDir)

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

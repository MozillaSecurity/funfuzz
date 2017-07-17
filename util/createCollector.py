#!/usr/bin/env python
# coding=utf-8
# pylint: disable=import-error,invalid-name,line-too-long,missing-docstring,wrong-import-position
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import absolute_import, print_function

import os
import sys


THIS_SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

fuzzManagerPath = os.path.abspath(os.path.join(THIS_SCRIPT_DIRECTORY, os.pardir, os.pardir, 'FuzzManager'))
if not os.path.exists(fuzzManagerPath):
    print("Please check out Lithium and FuzzManager side-by-side with funfuzz. Links in https://github.com/MozillaSecurity/funfuzz/#setup")
    sys.exit(2)
sys.path.append(fuzzManagerPath)
from Collector.Collector import Collector


def createCollector(tool):
    assert tool == "jsfunfuzz"
    cacheDir = os.path.normpath(os.path.expanduser(os.path.join("~", "sigcache")))
    try:
        os.mkdir(cacheDir)
    except OSError:
        pass  # cacheDir already exists
    collector = Collector(sigCacheDir=cacheDir, tool=tool)
    return collector


def printCrashInfo(crashInfo):
    if crashInfo.createShortSignature() != "No crash detected":
        print()
        print("crashInfo:")
        print("  Short Signature: %s" % crashInfo.createShortSignature())
        print("  Class name: %s" % crashInfo.__class__.__name__)   # "NoCrashInfo", etc
        print("  Stack trace: %r" % (crashInfo.backtrace,))
        print()


def printMatchingSignature(match):
    print("Matches signature in FuzzManager:")
    print("  Signature description: %s" % match[1].get('shortDescription'))
    print("  Signature file: %s" % match[0])
    print()

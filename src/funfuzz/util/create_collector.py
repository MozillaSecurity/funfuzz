# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Functions here make use of a Collector created from FuzzManager.
"""

from __future__ import absolute_import, print_function  # isort:skip

import os

from Collector.Collector import Collector


def createCollector(tool):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    assert tool == "jsfunfuzz"
    cache_dir = os.path.normpath(os.path.expanduser(os.path.join("~", "sigcache")))
    try:
        os.mkdir(cache_dir)
    except OSError:
        pass  # cache_dir already exists
    collector = Collector(sigCacheDir=cache_dir, tool=tool)
    return collector


def printCrashInfo(crashInfo):  # pylint: disable=invalid-name,missing-docstring
    if crashInfo.createShortSignature() != "No crash detected":
        print()
        print("crashInfo:")
        print("  Short Signature: %s" % crashInfo.createShortSignature())
        print("  Class name: %s" % crashInfo.__class__.__name__)   # "NoCrashInfo", etc
        print("  Stack trace: %r" % (crashInfo.backtrace,))
        print()


def printMatchingSignature(match):  # pylint: disable=invalid-name,missing-docstring
    print("Matches signature in FuzzManager:")
    print("  Signature description: %s" % match[1].get("shortDescription"))
    print("  Signature file: %s" % match[0])
    print()

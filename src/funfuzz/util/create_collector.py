# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Functions here make use of a Collector created from FuzzManager.
"""

from pathlib import Path

from Collector.Collector import Collector


def make_collector():
    """Creates a jsfunfuzz collector specifying ~/sigcache as the signature cache dir

    Returns:
        Collector: jsfunfuzz collector object
    """
    sigcache_path = Path.home() / "sigcache"
    sigcache_path.mkdir(exist_ok=True)  # pylint: disable=no-member
    return Collector(sigCacheDir=str(sigcache_path), tool="jsfunfuzz")


def printCrashInfo(crashInfo):  # pylint: disable=invalid-name,missing-docstring
    if crashInfo.createShortSignature() != "No crash detected":
        print()
        print("crashInfo:")
        print(f"  Short Signature: {crashInfo.createShortSignature()}")
        print(f"  Class name: {crashInfo.__class__.__name__}")   # "NoCrashInfo", etc
        print(f"  Stack trace: {crashInfo.backtrace}")
        print()


def printMatchingSignature(match):  # pylint: disable=invalid-name,missing-docstring
    print("Matches signature in FuzzManager:")
    print(f'  Signature description: {match[1].get("shortDescription")}')
    print(f"  Signature file: {match[0]}")
    print()

# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Functions here make use of a Collector created from FuzzManager.
"""

from pathlib import Path
from time import sleep

from Collector.Collector import Collector


def make_collector():
    """Creates a jsfunfuzz collector specifying ~/sigcache as the signature cache dir

    Returns:
        Collector: jsfunfuzz collector object
    """
    sigcache_path = Path.home() / "sigcache"
    sigcache_path.mkdir(exist_ok=True)
    return Collector(sigCacheDir=str(sigcache_path), tool="jsfunfuzz")


def printCrashInfo(crashInfo):  # pylint: disable=invalid-name,missing-docstring
    if crashInfo.createShortSignature() != "No crash detected":
        print()
        print("crashInfo:")
        print(f"  Short Signature: {crashInfo.createShortSignature()}")
        print(f"  Class name: {crashInfo.__class__.__name__}")   # "NoCrashInfo", etc
        print(f"  Stack trace: {crashInfo.backtrace!r}")
        print()


def printMatchingSignature(match):  # pylint: disable=invalid-name,missing-docstring
    print("Matches signature in FuzzManager:")
    print(f'  Signature description: {match[1].get("shortDescription")}')
    print(f"  Signature file: {match[0]}")
    print()


def submit_collector(collector, crash_info, testcase, quality, meta_data=None):
    """Use exponential backoff for FuzzManager submission. Adapted from https://stackoverflow.com/a/23961254/445241

    Args:
        collector (class): Collector for FuzzManager
        crash_info (object): Crash info object
        testcase (Path): Path to the testcase to be submitted
        quality (int): Quality specified as a number when submitting to FuzzManager
        meta_data (dict): Metadata when submitting testcase, if any
    """
    if meta_data is None:
        meta_data = {}
    sleep_time = 2
    for _ in range(0, 99):
        try:
            collector.submit(crash_info, str(testcase), quality, metaData=meta_data)
            break
        except RuntimeError:
            # Sample error via Reporter:
            # RuntimeError: Server unexpectedly responded with status code 500: <h1>Server Error (500)</h1>
            sleep(sleep_time)
            sleep_time *= 2  # exponential backoff

# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Functions here make use of a Collector created from FuzzManager.
"""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import logging
import sys

from Collector.Collector import Collector

if sys.version_info.major == 2:
    from pathlib2 import Path
else:
    from pathlib import Path  # pylint: disable=import-error

FUNFUZZ_LOG = logging.getLogger("funfuzz")
logging.basicConfig(level=logging.DEBUG)


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
        FUNFUZZ_LOG.info("\n")
        FUNFUZZ_LOG.info("crashInfo:")
        FUNFUZZ_LOG.info("  Short Signature: %s", crashInfo.createShortSignature())
        FUNFUZZ_LOG.info("  Class name: %s", crashInfo.__class__.__name__)   # "NoCrashInfo", etc
        FUNFUZZ_LOG.info("  Stack trace: %r", crashInfo.backtrace.rstrip())
        FUNFUZZ_LOG.info("\n")


def printMatchingSignature(match):  # pylint: disable=invalid-name,missing-docstring
    FUNFUZZ_LOG.info("Matches signature in FuzzManager:")
    FUNFUZZ_LOG.info("  Signature description: %s", match[1].get("shortDescription"))
    FUNFUZZ_LOG.info("  Signature file: %s", match[0])
    FUNFUZZ_LOG.info("\n")

# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the run_ccoverage.py file."""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import logging
import sys

import funfuzz

if sys.version_info.major == 2:
    import backports.tempfile as tempfile  # pylint: disable=import-error,no-name-in-module
    from pathlib2 import Path
else:
    from pathlib import Path  # pylint: disable=import-error
    import tempfile


FUNFUZZ_LOG = logging.getLogger("run_ccoverage_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


def test_get_coverage_build():
    """Ensure we retrieved a coverage build."""
    with tempfile.TemporaryDirectory(suffix="funfuzzcovtest") as dirpath:
        dirpath = Path(dirpath)
        funfuzz.ccoverage.get_build.get_coverage_build(dirpath, test_parse_args())


def test_get_grcov():
    """Ensure we retrieved a grcov binary."""
    with tempfile.TemporaryDirectory(suffix="funfuzzcovtest") as dirpath:
        dirpath = Path(dirpath)
        funfuzz.ccoverage.get_build.get_grcov(dirpath, test_parse_args())


def test_parse_args():  # pylint: disable=missing-return-type-doc
    """Test argument parsing.

    Returns:
        (class): Namespace of argparse parameters.
    """
    return funfuzz.run_ccoverage.parse_args(
        args=["--url", "https://build.fuzzing.mozilla.org/builds/jsshell-mc-64-opt-gcov.zip"])

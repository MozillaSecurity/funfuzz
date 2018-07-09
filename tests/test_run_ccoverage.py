# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the run_ccoverage.py file."""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import logging
import unittest

from _pytest.monkeypatch import MonkeyPatch
import distro
from pkg_resources import parse_version
import pytest

import funfuzz

FUNFUZZ_TEST_LOG = logging.getLogger("run_ccoverage_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


def mock_ccov_time():
    """Overwrite the ccov_time function to return a shorter time to test code coverage.

    Returns:
        int: Number of seconds to run code coverage
    """
    return 3


class RunCcoverageTests(unittest.TestCase):
    """"TestCase class for functions in run_ccoverage.py"""
    monkeypatch = MonkeyPatch()

    @pytest.mark.skipif(distro.linux_distribution()[0] == "Ubuntu" and
                        parse_version(distro.linux_distribution()[1]) < parse_version("16.04"),
                        reason="Code coverage binary crashes in 14.04 Trusty but works in 16.04 Xenial and up")
    @pytest.mark.slow
    def test_main(self):
        """Run run_ccoverage with test parameters."""
        RunCcoverageTests.monkeypatch.setattr(funfuzz.ccoverage.gatherer, "ccov_time", mock_ccov_time)

        build_url = "https://build.fuzzing.mozilla.org/builds/jsshell-mc-64-opt-gcov.zip"
        # run_ccoverage's main method does not actually return anything.
        self.assertTrue(not funfuzz.run_ccoverage.main(argparse_args=["--url", build_url]))

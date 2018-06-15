# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the run_ccoverage.py file."""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import logging
import unittest

import funfuzz

FUNFUZZ_TEST_LOG = logging.getLogger("run_ccoverage_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


class RunCcoverageTests(unittest.TestCase):
    """"TestCase class for functions in run_ccoverage.py"""
    @pytest.mark.skip(reason="disable for now until actual use")
    def test_main(self):
        """Run run_ccoverage with test parameters."""
        build_url = "https://build.fuzzing.mozilla.org/builds/jsshell-mc-64-opt-gcov.zip"
        # run_ccoverage's main method does not actually return anything.
        self.assertTrue(not funfuzz.run_ccoverage.main(argparse_args=["--url", build_url]))

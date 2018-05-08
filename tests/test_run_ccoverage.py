# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the run_ccoverage.py file."""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import logging

import funfuzz

FUNFUZZ_TEST_LOG = logging.getLogger("run_ccoverage_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


def test_main():
    """Run run_ccoverage with test parameters."""
    funfuzz.run_ccoverage.main(
        argparse_args=["--url", "https://build.fuzzing.mozilla.org/builds/jsshell-mc-64-opt-gcov.zip"])

# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the run_ccoverage.py file."""

import logging
import unittest

from _pytest.monkeypatch import MonkeyPatch
from pkg_resources import parse_version
import pytest

import distro
from funfuzz import run_ccoverage
from funfuzz.ccoverage import gatherer

FUNFUZZ_TEST_LOG = logging.getLogger("run_ccoverage_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


class RunCcoverageTests(unittest.TestCase):
    """"TestCase class for functions in run_ccoverage.py"""

    @staticmethod
    @pytest.mark.skipif(distro.linux_distribution()[0] == "Ubuntu" and
                        parse_version(distro.linux_distribution()[1]) < parse_version("16.04"),
                        reason="Code coverage binary crashes in 14.04 Trusty but works in 16.04 Xenial and up")
    @pytest.mark.slow
    def test_main():
        """Run run_ccoverage with test parameters."""
        build_url = "https://build.fuzzing.mozilla.org/builds/jsshell-mc-64-opt-gcov.zip"

        monkey = MonkeyPatch()
        with monkey.context() as monkey_context:
            monkey_context.setattr(gatherer, "RUN_COV_TIME", 3)
            monkey_context.setattr("funfuzz.ccoverage.reporter.report_coverage",
                                   lambda x: FUNFUZZ_TEST_LOG.info("Simulation: cov_result_file report is: %s", x))
            monkey_context.setattr("funfuzz.ccoverage.reporter.disable_pool",
                                   lambda: FUNFUZZ_TEST_LOG.info("Simulation: Pool disabled"))

            run_ccoverage.main(argparse_args=["--url", build_url, "--report"])

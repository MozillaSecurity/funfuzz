# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the run_ccoverage.py file."""

import logging

from pkg_resources import parse_version
import pytest

import distro
from funfuzz import run_ccoverage
from funfuzz.ccoverage import gatherer
from funfuzz.ccoverage import reporter

FUNFUZZ_TEST_LOG = logging.getLogger("run_ccoverage_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.ERROR)


@pytest.mark.skipif(distro.linux_distribution()[0] == "Ubuntu" and
                    parse_version(distro.linux_distribution()[1]) < parse_version("16.04"),
                    reason="Code coverage binary crashes in 14.04 Trusty but works in 16.04 Xenial and up")
@pytest.mark.slow
def test_main(monkeypatch):
    """Run run_ccoverage with test parameters.

    Args:
        monkeypatch (class): Fixture from pytest for monkeypatching some variables/functions
    """
    build_url = "https://build.fuzzing.mozilla.org/builds/jsshell-mc-64-opt-gcov.zip"

    monkeypatch.setattr(gatherer, "RUN_COV_TIME", 3)
    assert gatherer.RUN_COV_TIME == 3
    monkeypatch.setattr(reporter, "report_coverage", lambda _: "hit")
    assert reporter.report_coverage("") == "hit"
    monkeypatch.setattr(reporter, "disable_pool", lambda: "hit")
    assert reporter.disable_pool() == "hit"

    run_ccoverage.main(argparse_args=["--url", build_url, "--report"])

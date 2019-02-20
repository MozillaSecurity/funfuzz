# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the sm_compile_helpers.py file."""

import logging
from pathlib import Path
import platform

import pytest

from funfuzz import util

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.ERROR)

# For ICU tests
M4_REL_DIR = Path("build") / "autoconf"
M4_REL_PATH = M4_REL_DIR / "icu.m4"
MC_ICU_M4 = Path("~/trees/mozilla-central").expanduser() / M4_REL_PATH


@pytest.mark.skipif(platform.system() == "Windows", reason="Windows on Travis is still new and experimental")
def test_autoconf_run(tmpdir):
    """Test the autoconf runs properly.

    Args:
        tmpdir (class): Fixture from pytest for creating a temporary directory
    """
    tmpdir = Path(tmpdir)
    # configure.in is required by autoconf2.13
    (tmpdir / "configure.in").touch()  # pylint: disable=no-member
    util.sm_compile_helpers.autoconf_run(tmpdir)


def test_ensure_cache_dir():
    """Test the shell-cache dir is created properly if it does not exist, and things work even though it does."""
    assert util.sm_compile_helpers.ensure_cache_dir(None).is_dir()
    assert util.sm_compile_helpers.ensure_cache_dir(Path.home()).is_dir()  # pylint: disable=no-member

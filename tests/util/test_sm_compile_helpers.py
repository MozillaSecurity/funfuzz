# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the sm_compile_helpers.py file."""

import io
import logging
from pathlib import Path
import platform
import shutil

import pytest

from funfuzz import util

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.ERROR)

# For ICU tests
M4_REL_DIR = Path("build") / "autoconf"
M4_REL_PATH = M4_REL_DIR / "icu.m4"
MC_ICU_M4 = Path("~/trees/mozilla-central").expanduser() / M4_REL_PATH


@pytest.fixture
@pytest.mark.slow  # Workaround for Travis as we only have mozilla-central and hence icu.m4, available on slow tests
@pytest.mark.skipif(platform.system() != "Linux",
                    reason="sed version check only works with GNU sed, not macOS BSD sed")
def test_icu_m4_replace(tmpdir):
    """Test the bionic change replaces properly.

    Args:
        tmpdir (class): Fixture from pytest for creating a temporary directory
    """
    tmpdir = Path(tmpdir)
    Path.mkdir(tmpdir / M4_REL_DIR, parents=True)
    m4_replace_abs_path = tmpdir / M4_REL_PATH

    shutil.copy2(MC_ICU_M4, m4_replace_abs_path)

    util.sm_compile_helpers.icu_m4_replace(tmpdir)

    # Double check
    with io.open(str(m4_replace_abs_path), "r", encoding="utf-8", errors="replace") as f:
        found = False
        for line in f.readlines():
            if r"s/^[[[:space:]]]*#[[:space:]]*define[[:space:]][[:space:]]*U_ICU_VERSION_MAJOR_NUM" in line:
                found = True
                break
        assert found

    m4_replace_abs_path.unlink()


@pytest.mark.slow  # Workaround for Travis as we only have mozilla-central and hence icu.m4, available on slow tests
@pytest.mark.skipif(platform.system() != "Linux",
                    reason="sed version check only works with GNU sed, not macOS BSD sed")
def test_icu_m4_undo(test_icu_m4_replace, tmpdir):  # pylint: disable=redefined-outer-name,unused-argument
    """Test the bionic change reverse-replaces properly.

    Args:
        test_icu_m4_replace (class): Custom pytest fixture from this module
        tmpdir (class): Fixture from pytest for creating a temporary directory
    """
    tmpdir = Path(tmpdir)
    assert (tmpdir / M4_REL_DIR).is_dir()  # This dir should have been created by the test_icu_m4_replace fixture above
    m4_undo_abs_path = tmpdir / M4_REL_PATH

    shutil.copy2(MC_ICU_M4, m4_undo_abs_path)

    util.sm_compile_helpers.icu_m4_replace(tmpdir)
    util.sm_compile_helpers.icu_m4_undo(tmpdir)

    # Double check
    with io.open(str(m4_undo_abs_path), "r", encoding="utf-8", errors="replace") as f:
        found = False
        for line in f.readlines():
            if r"s/^[[:space:]]*#[[:space:]]*define[[:space:]][[:space:]]*U_ICU_VERSION_MAJOR_NUM" in line:
                found = True
                break
        assert found

    m4_undo_abs_path.unlink()


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

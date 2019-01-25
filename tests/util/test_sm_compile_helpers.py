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
import tempfile
import unittest

import pytest

from funfuzz import util

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


class SmCompileHelpersTests(unittest.TestCase):
    """"TestCase class for functions in sm_compile_helpers.py"""
    tmp_dir_object = tempfile.TemporaryDirectory(suffix="_sm_compile_helpers_test")
    tmp_dir = Path(tmp_dir_object.name)

    # For ICU tests
    icu_m4_rel_dir = Path("build") / "autoconf"
    icu_m4_rel_path = icu_m4_rel_dir / "icu.m4"
    mc_icu_m4 = Path("~/trees/mozilla-central").expanduser() / icu_m4_rel_path
    icu_m4_test_abs_path = tmp_dir / icu_m4_rel_path

    @classmethod
    def setup_class(cls):
        """Copy over the ICU m4 file from mozilla-central."""
        icu_m4_test_dir = cls.tmp_dir / cls.icu_m4_rel_dir
        Path.mkdir(icu_m4_test_dir, parents=True)

    @classmethod
    def teardown_class(cls):
        """Remove the temporary directory on test completion."""
        cls.tmp_dir_object.cleanup()

    @pytest.mark.slow  # Workaround for Travis as we only have mozilla-central and hence icu.m4, available on slow tests
    @pytest.mark.skipif(platform.system() != "Linux",
                        reason="sed version check only works with GNU sed, not macOS BSD sed")
    def test_icu_m4_replace(self):
        """Test the bionic change replaces properly."""
        shutil.copy2(self.mc_icu_m4, self.icu_m4_test_abs_path)

        util.sm_compile_helpers.icu_m4_replace(self.tmp_dir)

        # Double check
        with io.open(str(self.icu_m4_test_abs_path), "r", encoding="utf-8", errors="replace") as f:
            found = False
            for line in f.readlines():
                if r"s/^[[[:space:]]]*#[[:space:]]*define[[:space:]][[:space:]]*U_ICU_VERSION_MAJOR_NUM" in line:
                    found = True
                    break
            assert found

        self.icu_m4_test_abs_path.unlink()

    @pytest.mark.slow  # Workaround for Travis as we only have mozilla-central and hence icu.m4, available on slow tests
    @pytest.mark.skipif(platform.system() != "Linux",
                        reason="sed version check only works with GNU sed, not macOS BSD sed")
    def test_icu_m4_undo(self):
        """Test the bionic change reverse-replaces properly."""
        shutil.copy2(self.mc_icu_m4, self.icu_m4_test_abs_path)

        util.sm_compile_helpers.icu_m4_replace(self.tmp_dir)
        util.sm_compile_helpers.icu_m4_undo(self.tmp_dir)

        # Double check
        with io.open(str(self.icu_m4_test_abs_path), "r", encoding="utf-8", errors="replace") as f:
            found = False
            for line in f.readlines():
                if r"s/^[[:space:]]*#[[:space:]]*define[[:space:]][[:space:]]*U_ICU_VERSION_MAJOR_NUM" in line:
                    found = True
                    break
            assert found

        self.icu_m4_test_abs_path.unlink()

    @pytest.mark.skipif(platform.system() == "Windows", reason="Windows on Travis is still new and experimental")
    def test_autoconf_run(self):
        """Test the autoconf runs properly."""
        # configure.in is required by autoconf2.13
        (self.tmp_dir / "configure.in").touch()  # pylint: disable=no-member
        util.sm_compile_helpers.autoconf_run(self.tmp_dir)

    @staticmethod
    def test_ensure_cache_dir():
        """Test the shell-cache dir is created properly if it does not exist, and things work even though it does."""
        assert util.sm_compile_helpers.ensure_cache_dir(None).is_dir()
        assert util.sm_compile_helpers.ensure_cache_dir(Path.home()).is_dir()  # pylint: disable=no-member

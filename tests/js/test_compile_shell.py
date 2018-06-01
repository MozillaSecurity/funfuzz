# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the compile_shell.py file."""

from __future__ import absolute_import, unicode_literals  # isort:skip

import logging
import os
import platform
import sys
import unittest

import pytest

from funfuzz import js
from funfuzz import util

if sys.version_info.major == 2:
    import backports.tempfile as tempfile  # pylint: disable=import-error,no-name-in-module
    from functools32 import lru_cache  # pylint: disable=import-error
    from pathlib2 import Path
else:
    from functools import lru_cache  # pylint: disable=no-name-in-module
    from pathlib import Path  # pylint: disable=import-error
    import tempfile

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


class CompileShellTests(unittest.TestCase):
    """"TestCase class for functions in compile_shell.py"""
    # Paths
    mc_hg_repo = Path.home() / "trees" / "mozilla-central"
    shell_cache = Path.home() / "shell-cache"

    def test_autoconf_run():  # pylint: disable=no-method-argument
        """Test the autoconf runs properly."""
        with tempfile.TemporaryDirectory(suffix="autoconf_run_test") as tmp_dir:
            tmp_dir = Path(tmp_dir)

            (tmp_dir / "configure.in").touch()  # configure.in is required by autoconf2.13
            js.compile_shell.autoconf_run(tmp_dir)

    def test_ensure_cache_dir(self):
        """Test the shell-cache dir is created properly if it does not exist."""
        self.assertTrue(js.compile_shell.ensure_cache_dir().is_dir())

    @pytest.mark.slow
    @lru_cache(maxsize=None)
    def test_shell_compile(self):
        """Test compilation of shells depending on the specified environment variable.

        Returns:
            Path: Path to the compiled shell.
        """
        self.assertTrue(self.mc_hg_repo.is_dir())  # pylint: disable=no-member
        # Change the repository location by uncommenting this line and specifying the right one
        # "-R ~/trees/mozilla-central/")

        default_parameters_debug = ("--enable-debug --disable-optimize --enable-more-deterministic "
                                    "--build-with-valgrind --enable-oom-breakpoint")
        # Remember to update the corresponding BUILD build parameters in .travis.yml as well
        build_opts = os.environ.get("BUILD", default_parameters_debug)

        opts_parsed = js.build_options.parse_shell_opts(build_opts)
        hg_hash_of_default = util.hg_helpers.get_repo_hash_and_id(opts_parsed.repo_dir)[0]
        # Ensure exit code is 0
        self.assertTrue(not js.compile_shell.CompiledShell(opts_parsed, hg_hash_of_default).run(["-b", build_opts]))

        if default_parameters_debug in build_opts:
            # Test compilation of a debug shell with determinism, valgrind and OOM breakpoint support.
            file_name = "js-dbg-optDisabled-64-dm-vg-oombp-linux-" + hg_hash_of_default
        elif "--disable-debug --disable-profiling --without-intl-api" in build_opts:
            # Test compilation of an opt shell with both profiling and Intl support disabled.
            # This set of builds should also have the following: 32-bit with ARM, with asan, and with clang
            file_name = "js-64-profDisabled-intlDisabled-linux-" + hg_hash_of_default

        js_bin_path = self.shell_cache / file_name / file_name
        if platform.system() == "Windows":
            js_bin_path.with_suffix(".exe")
        self.assertTrue(js_bin_path.is_file())

        return js_bin_path

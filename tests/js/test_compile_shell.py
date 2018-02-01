# coding=utf-8
# pylint: disable=invalid-name
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the compile_shell.py file."""

from __future__ import absolute_import, unicode_literals

import logging
import platform
import sys
import pytest  # pylint: disable=wrong-import-order

import funfuzz

if sys.version_info.major == 2:
    from pathlib2 import Path
else:
    from pathlib import Path  # pylint: disable=import-error

funfuzz_log = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)

MC_HG_REPO = Path.home() / "trees" / "mozilla-central"
SHELL_CACHE = Path.home() / "shell-cache"


@pytest.mark.slow
def test_compile_shell_A_dbg():
    """Test compilation of a debug shell with determinism, valgrind and OOM breakpoint support."""
    assert MC_HG_REPO.is_dir()  # pylint: disable=no-member
    # Remember to update the expected binary filename
    build_opts = ("--enable-debug --disable-optimize --enable-more-deterministic "
                  "--build-with-valgrind --enable-oom-breakpoint")
    # Change the repository location by uncommenting this line and specifying the right one
    # "-R ~/trees/mozilla-central/")
    build_opts_processed = funfuzz.js.build_options.parseShellOptions(build_opts)
    hg_hash_of_default = funfuzz.util.hg_helpers.getRepoHashAndId(build_opts_processed.repoDir)[0]

    fz = funfuzz.js.compile_shell.CompiledShell(build_opts_processed, hg_hash_of_default)

    result = fz.run(["-b", build_opts])
    assert result == 0

    file_name = "js-dbg-optDisabled-64-dm-vg-oombp-linux-" + hg_hash_of_default
    js_bin_path = SHELL_CACHE / file_name / file_name
    if platform.system() == "Windows":
        js_bin_path.with_suffix(".exe")
    assert js_bin_path.is_file()


@pytest.mark.slow
def test_compile_shell_B_opt():
    """Test compilation of an opt shell with both profiling and Intl support disabled."""
    assert MC_HG_REPO.is_dir()  # pylint: disable=no-member
    # Remember to update the expected binary filename
    build_opts = ("--disable-debug --disable-profiling --without-intl-api")
    # Change the repository location by uncommenting this line and specifying the right one
    # "-R ~/trees/mozilla-central/")
    build_opts_processed = funfuzz.js.build_options.parseShellOptions(build_opts)
    hg_hash_of_default = funfuzz.util.hg_helpers.getRepoHashAndId(build_opts_processed.repoDir)[0]

    fz = funfuzz.js.compile_shell.CompiledShell(build_opts_processed, hg_hash_of_default)

    # This set of builds should also have the following: 32-bit with ARM, with asan, and with clang
    result = fz.run(["-b", build_opts])
    assert result == 0

    file_name = "js-64-profDisabled-intlDisabled-linux-" + hg_hash_of_default
    js_bin_path = SHELL_CACHE / file_name / file_name
    if platform.system() == "Windows":
        js_bin_path.with_suffix(".exe")
    assert js_bin_path.is_file()

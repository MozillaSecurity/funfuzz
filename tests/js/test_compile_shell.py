# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the compile_shell.py file."""

from functools import lru_cache
import logging
import os
from pathlib import Path
import platform

import pytest

from funfuzz import js
from funfuzz import util

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.ERROR)

# Paths
MC_PATH = Path.home() / "trees" / "mozilla-central"
SHELL_CACHE = Path.home() / "shell-cache"


@pytest.mark.slow
@lru_cache(maxsize=None)
def test_shell_compile():
    """Test compilation of shells depending on the specified environment variable.

    Returns:
        Path: Path to the compiled shell.
    """
    assert MC_PATH.is_dir()  # pylint: disable=no-member
    # Change the repository location by uncommenting this line and specifying the right one
    # "-R ~/trees/mozilla-central/")

    default_parameters_debug = ("--enable-debug --disable-optimize --enable-more-deterministic "
                                "--enable-valgrind --enable-oom-breakpoint")
    # Remember to update the corresponding BUILD build parameters in .travis.yml as well
    build_opts = os.getenv("BUILD", default_parameters_debug)

    opts_parsed = js.build_options.parse_shell_opts(build_opts)
    hg_hash_of_default = util.hg_helpers.get_repo_hash_and_id(opts_parsed.repo_dir)[0]
    # Ensure exit code is 0
    assert not js.compile_shell.CompiledShell(opts_parsed, hg_hash_of_default).run(["-b", build_opts])

    file_name = None
    if default_parameters_debug in build_opts:
        # Test compilation of a debug shell with determinism, valgrind and OOM breakpoint support.
        file_name = f"js-dbg-optDisabled-64-dm-vg-oombp-linux-x86_64-{hg_hash_of_default}"
    elif "--disable-debug --disable-profiling --without-intl-api" in build_opts:
        # Test compilation of an opt shell with both profiling and Intl support disabled.
        # This set of builds should also have the following: 32-bit with ARM, with asan, and with clang
        file_name = f"js-64-profDisabled-intlDisabled-linux-x86_64-{hg_hash_of_default}"

    js_bin_path = SHELL_CACHE / file_name / file_name
    if platform.system() == "Windows":
        js_bin_path.with_suffix(".exe")
    assert js_bin_path.is_file()

    return js_bin_path

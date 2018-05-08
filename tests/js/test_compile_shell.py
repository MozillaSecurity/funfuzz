# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the compile_shell.py file."""

from __future__ import absolute_import, unicode_literals  # isort:skip

import logging
import os
import sys

import pytest

import funfuzz

if sys.version_info.major == 2:
    from functools32 import lru_cache  # pylint: disable=import-error
else:
    from functools import lru_cache  # pylint: disable=no-name-in-module

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)

IS_CI_NO_SLOW = ("CI" in os.environ and os.environ["CI"] == "true" and
                 "NO_SLOW" in os.environ and os.environ["NO_SLOW"] == "true")
SLOW_TEST = pytest.mark.xfail(IS_CI_NO_SLOW,
                              raises=AssertionError,
                              reason="NO_SLOW is true, so skipping this test on Travis CI.")


@SLOW_TEST
@lru_cache(maxsize=None)
def test_shell_compile():
    """Test compilation of shells depending on the specified environment variable.

    Returns:
        str: Path to the compiled shell.
    """
    assert os.path.isdir(os.path.join(os.path.expanduser("~"), "trees", "mozilla-central"))
    # Change the repository location by uncommenting this line and specifying the right one
    # "-R ~/trees/mozilla-central/")

    default_parameters_debug = ("--enable-debug --disable-optimize --enable-more-deterministic "
                                "--build-with-valgrind --enable-oom-breakpoint")
    # Remember to update the corresponding BUILD build parameters in .travis.yml as well
    build_opts = os.environ.get("BUILD", default_parameters_debug)

    opts_parsed = funfuzz.js.build_options.parseShellOptions(build_opts)
    hg_hash_of_default = funfuzz.util.hg_helpers.getRepoHashAndId(opts_parsed.repoDir)[0]
    # Ensure exit code is 0
    assert not funfuzz.js.compile_shell.CompiledShell(opts_parsed, hg_hash_of_default).run(["-b", build_opts])

    if default_parameters_debug in build_opts:
        # Test compilation of a debug shell with determinism, valgrind and OOM breakpoint support.
        file_name = "js-dbg-optDisabled-64-dm-vg-oombp-linux-" + hg_hash_of_default
    elif "--disable-debug --disable-profiling --without-intl-api" in build_opts:
        # Test compilation of an opt shell with both profiling and Intl support disabled.
        # This set of builds should also have the following: 32-bit with ARM, with asan, and with clang
        file_name = "js-64-profDisabled-intlDisabled-linux-" + hg_hash_of_default

    compiled_bin = os.path.join(os.path.expanduser("~"), "shell-cache", file_name, file_name)
    assert os.path.isfile(compiled_bin)

    return compiled_bin

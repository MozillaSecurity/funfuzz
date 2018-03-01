# coding=utf-8
# pylint: disable=invalid-name,missing-docstring
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import absolute_import, unicode_literals

import logging
import os

import funfuzz

funfuzz_log = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


def get_current_shell_path():
    """Returns the path to the currently built shell."""
    assert os.path.isdir(os.path.join(os.path.expanduser("~"), "trees", "mozilla-central"))
    # Remember to update the expected binary filename
    build_opts = ("--enable-debug --disable-optimize --enable-more-deterministic "
                  "--build-with-valgrind --enable-oom-breakpoint")
    # Change the repository location by uncommenting this line and specifying the right one
    # "-R ~/trees/mozilla-central/")
    build_opts_processed = funfuzz.js.build_options.parseShellOptions(build_opts)
    hg_hash_of_default = funfuzz.util.hg_helpers.getRepoHashAndId(build_opts_processed.repoDir)[0]

    return os.path.join(os.path.expanduser("~"), "shell-cache",
                        "js-dbg-optDisabled-64-dm-vg-oombp-linux-" + hg_hash_of_default,
                        "js-dbg-optDisabled-64-dm-vg-oombp-linux-" + hg_hash_of_default)


def test_basic_flag_sets():
    """Test that we are able to obtain a basic set of shell runtime flags for fuzzing."""
    important_flag_set = ["--fuzzing-safe", "--no-threads", "--ion-eager"]  # Important flag set combination
    assert important_flag_set in funfuzz.js.shell_flags.basic_flag_sets(get_current_shell_path())


def test_chance():
    """Test that the chance function works as intended."""
    assert funfuzz.js.shell_flags.chance(0.6, always=True)
    assert funfuzz.js.shell_flags.chance(0.1, always=True)


def test_shell_supports_flag():
    """Test that the shell does support flags as intended."""
    assert funfuzz.js.shell_flags.shell_supports_flag(get_current_shell_path(), "--fuzzing-safe")

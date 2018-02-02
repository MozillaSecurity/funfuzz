# coding=utf-8
# pylint: disable=invalid-name,missing-docstring
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import absolute_import

import logging
import os

import funfuzz

funfuzz_log = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


def test_basic_flag_sets():
    """Test that we are able to obtain a basic set of shell runtime flags for fuzzing."""
    assert os.path.isdir(os.path.join(os.path.expanduser("~"), "trees", "mozilla-central"))
    # Remember to update the expected binary filename
    build_opts = ("--enable-debug --disable-optimize --enable-more-deterministic "
                  "--build-with-valgrind --enable-oom-breakpoint")
    # Change the repository location by uncommenting this line and specifying the right one
    # "-R ~/trees/mozilla-central/")
    build_opts_processed = funfuzz.js.build_options.parseShellOptions(build_opts)
    hg_hash_of_default = funfuzz.util.hg_helpers.getRepoHashAndId(build_opts_processed.repoDir)[0]

    shell_location = os.path.join(os.path.expanduser("~"), "shell-cache",
                                  "js-dbg-optDisabled-64-dm-vg-oombp-linux-" + hg_hash_of_default,
                                  "js-dbg-optDisabled-64-dm-vg-oombp-linux-" + hg_hash_of_default)

    important_flag_set = ["--fuzzing-safe", "--no-threads", "--ion-eager"]  # Important flag set combination
    assert important_flag_set in funfuzz.js.shell_flags.basic_flag_sets(shell_location)

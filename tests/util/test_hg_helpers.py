# coding=utf-8
# pylint: disable=invalid-name,missing-docstring
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import absolute_import, unicode_literals

import logging

import funfuzz

funfuzz_log = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


def test_get_cset_hash_from_bisect_msg():
    """Test that we are able to extract the changeset hash from bisection output."""
    assert funfuzz.util.hg_helpers.get_cset_hash_from_bisect_msg("x 12345:abababababab") == "abababababab"
    assert funfuzz.util.hg_helpers.get_cset_hash_from_bisect_msg("x 12345:123412341234") == "123412341234"
    assert funfuzz.util.hg_helpers.get_cset_hash_from_bisect_msg("12345:abababababab y") == "abababababab"
    assert (funfuzz.util.hg_helpers.get_cset_hash_from_bisect_msg(
        "Testing changeset 41831:4f4c01fb42c3 (2 changesets remaining, ~1 tests)") == "4f4c01fb42c3")

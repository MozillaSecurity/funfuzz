# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the hg_helpers.py file."""

import logging
from pathlib import Path
import re

import pytest

from funfuzz.util import hg_helpers

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.ERROR)

TREES_PATH = Path.home() / "trees"


def test_get_cset_hash_in_bisectmsg():
    """Test that we are able to extract the changeset hash from bisection output."""
    assert hg_helpers.get_cset_hash_from_bisect_msg("x 12345:abababababab") == "abababababab"
    assert hg_helpers.get_cset_hash_from_bisect_msg("x 12345:123412341234") == "123412341234"
    assert hg_helpers.get_cset_hash_from_bisect_msg("12345:abababababab y") == "abababababab"
    assert hg_helpers.get_cset_hash_from_bisect_msg(
        "Testing changeset 41831:4f4c01fb42c3 (2 changesets remaining, ~1 tests)") == "4f4c01fb42c3"
    with pytest.raises(ValueError) as excinfo:
        hg_helpers.get_cset_hash_from_bisect_msg("1a2345 - abababababab")
        assert re.search(r"^Bisection output format required for hash extraction unavailable. "
                         "The variable msg is:", excinfo.value)


# pylint: disable=no-member
@pytest.mark.skipif(not (TREES_PATH / "mozilla-central" / ".hg" / "hgrc").is_file(),
                    reason="requires a Mozilla Mercurial repository")
def test_hgrc_repo_name():
    """Test that we are able to extract the repository name from the hgrc file."""
    assert hg_helpers.hgrc_repo_name(TREES_PATH / "mozilla-central") == "mozilla-central"

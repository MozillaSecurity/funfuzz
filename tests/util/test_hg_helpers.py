# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the hg_helpers.py file."""

from __future__ import absolute_import, unicode_literals  # isort:skip

import logging
import sys
import unittest

import pytest

from funfuzz.util import hg_helpers

if sys.version_info.major == 2:
    from pathlib2 import Path
else:
    from pathlib import Path  # pylint: disable=import-error

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


class TestCase(unittest.TestCase):
    """"TestCase class for general functions, e.g. backport ones."""
    if sys.version_info.major == 2:
        def assertRaisesRegex(self, *args, **kwds):  # pylint: disable=arguments-differ,invalid-name
            # pylint: disable=missing-param-doc,missing-return-doc,missing-return-type-doc
            """Adds support for raising exceptions with messages containing desired regex."""
            return self.assertRaisesRegexp(*args, **kwds)  # pylint: disable=deprecated-method


class HgHelpersTests(TestCase):
    """"TestCase class for functions in hg_helpers.py"""
    trees_location = Path.home() / "trees"

    def test_get_cset_hash_in_bisectmsg(self):
        """Test that we are able to extract the changeset hash from bisection output."""
        self.assertEqual(hg_helpers.get_cset_hash_from_bisect_msg("x 12345:abababababab"), "abababababab")
        self.assertEqual(hg_helpers.get_cset_hash_from_bisect_msg("x 12345:123412341234"), "123412341234")
        self.assertEqual(hg_helpers.get_cset_hash_from_bisect_msg("12345:abababababab y"), "abababababab")
        self.assertEqual(hg_helpers.get_cset_hash_from_bisect_msg(
            "Testing changeset 41831:4f4c01fb42c3 (2 changesets remaining, ~1 tests)"), "4f4c01fb42c3")
        with self.assertRaisesRegex(ValueError,
                                    (r"^Bisection output format required for hash extraction unavailable. "
                                     "The variable msg is:")):
            hg_helpers.get_cset_hash_from_bisect_msg("1a2345 - abababababab")

    @pytest.mark.skipif(not (trees_location / "mozilla-central" / ".hg" / "hgrc").is_file(),
                        reason="requires a Mozilla Mercurial repository")
    def test_hgrc_repo_name(self):
        """Test that we are able to extract the repository name from the hgrc file."""
        self.assertEqual(hg_helpers.hgrc_repo_name(self.trees_location / "mozilla-central"), "mozilla-central")

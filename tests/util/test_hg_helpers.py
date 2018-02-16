# coding=utf-8
# pylint: disable=invalid-name,missing-docstring
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import absolute_import, unicode_literals

import logging
import sys
import unittest

import funfuzz

funfuzz_log = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


class TestCase(unittest.TestCase):

    if sys.version_info.major == 2:

        def assertRaisesRegex(self, *args, **kwds):  # pylint: disable=arguments-differ
            # pylint: disable=missing-return-doc,missing-return-type-doc
            return self.assertRaisesRegexp(*args, **kwds)  # pylint: disable=deprecated-method


class HgHelpersTests(TestCase):

    def test_get_cset_hash_from_bisect_msg(self):
        """Test that we are able to extract the changeset hash from bisection output."""
        self.assertEqual(funfuzz.util.hg_helpers.get_cset_hash_from_bisect_msg("x 12345:abababababab"), "abababababab")
        self.assertEqual(funfuzz.util.hg_helpers.get_cset_hash_from_bisect_msg("x 12345:123412341234"), "123412341234")
        self.assertEqual(funfuzz.util.hg_helpers.get_cset_hash_from_bisect_msg("12345:abababababab y"), "abababababab")
        self.assertEqual(funfuzz.util.hg_helpers.get_cset_hash_from_bisect_msg(
            "Testing changeset 41831:4f4c01fb42c3 (2 changesets remaining, ~1 tests)"), "4f4c01fb42c3")
        with self.assertRaisesRegex(ValueError,
                                    (r"^Bisection output format required for hash extraction unavailable. "
                                     "The variable msg is:")):
            funfuzz.util.hg_helpers.get_cset_hash_from_bisect_msg("1a2345 - abababababab")

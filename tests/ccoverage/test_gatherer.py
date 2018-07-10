# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the gatherer.py file."""

from __future__ import absolute_import, unicode_literals  # isort:skip

import logging
import unittest

from funfuzz.ccoverage import gatherer

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


class GathererTests(unittest.TestCase):
    """"TestCase class for functions in gatherer.py"""

    @staticmethod
    def test_ccov_time():
        """Test that the time to run code coverage is as expected."""
        assert gatherer.ccov_time() == 85000

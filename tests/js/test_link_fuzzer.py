# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the link_fuzzer.py file."""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import io
import logging
import sys
import unittest

from funfuzz.js import link_fuzzer

if sys.version_info.major == 2:
    import backports.tempfile as tempfile  # pylint: disable=import-error,no-name-in-module
    from pathlib2 import Path  # pylint: disable=import-error
else:
    from pathlib import Path  # pylint: disable=import-error
    import tempfile

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


class LinkFuzzerTests(unittest.TestCase):
    """"TestCase class for functions in link_fuzzer.py"""
    @staticmethod
    def test_link_fuzzer():
        """Test that a full jsfunfuzz file can be created."""
        with tempfile.TemporaryDirectory(suffix="link_fuzzer_test") as tmp_dir:
            tmp_dir = Path(tmp_dir)
            jsfunfuzz_tmp = tmp_dir / "jsfunfuzz.js"

            link_fuzzer.link_fuzzer(jsfunfuzz_tmp)

            found = False
            with io.open(str(jsfunfuzz_tmp), "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if "It's looking good" in line:
                        found = True
                        break

            assert found

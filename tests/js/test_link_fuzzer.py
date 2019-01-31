# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the link_fuzzer.py file."""

import io
import logging
from pathlib import Path
import tempfile
import unittest

from funfuzz.js import link_fuzzer
from funfuzz.util.logging_helpers import get_logger

LOG_TEST_LINK_FUZZER = get_logger(__name__, level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.ERROR)


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

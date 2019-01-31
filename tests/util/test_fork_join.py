# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the fork_join.py file."""

import io
import logging
from pathlib import Path
import tempfile
import unittest

from funfuzz.util import fork_join

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.ERROR)


class ForkJoinTests(unittest.TestCase):
    """"TestCase class for functions in fork_join.py"""
    @staticmethod
    def test_log_name():
        """Test that incrementally numbered wtmp directories can be created"""
        with tempfile.TemporaryDirectory(suffix="make_wtmp_dir_test") as tmp_dir:
            tmp_dir = Path(tmp_dir)
            log_path = tmp_dir / "forkjoin-1-out.txt"

            with io.open(str(log_path), "w", encoding="utf-8", errors="replace") as f:
                f.writelines("test")

            assert fork_join.log_name(tmp_dir, 1, "out") == str(log_path)

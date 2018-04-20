# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the compile_shell.py file."""

from __future__ import absolute_import, unicode_literals  # isort:skip

import logging
import sys
import unittest

from funfuzz.util import os_ops

if sys.version_info.major == 2:
    import backports.tempfile as tempfile  # pylint: disable=import-error,no-name-in-module
    from pathlib2 import Path
else:
    from pathlib import Path  # pylint: disable=import-error
    import tempfile

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


class OsOpsTests(unittest.TestCase):
    """"TestCase class for functions in os_ops.py"""
    def test_make_wtmp_dir(self):
        """Test that incrementally numbered wtmp directories can be created"""
        with tempfile.TemporaryDirectory(suffix="make_wtmp_dir_test") as tmp_dir:
            tmp_dir = Path(tmp_dir)

            wtmp_dir_1 = os_ops.make_wtmp_dir(tmp_dir)
            self.assertTrue(wtmp_dir_1.is_dir())
            self.assertTrue(wtmp_dir_1.name.endswith("1"))

            wtmp_dir_2 = os_ops.make_wtmp_dir(tmp_dir)
            self.assertTrue(wtmp_dir_2.is_dir())
            self.assertTrue(wtmp_dir_2.name.endswith("2"))

            wtmp_dir_3 = os_ops.make_wtmp_dir(tmp_dir)
            self.assertTrue(wtmp_dir_3.is_dir())
            self.assertTrue(wtmp_dir_3.name.endswith("3"))

            wtmp_dir_4 = os_ops.make_wtmp_dir(tmp_dir)
            self.assertTrue(wtmp_dir_4.is_dir())
            self.assertTrue(wtmp_dir_4.name.endswith("4"))

# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the fork_join.py file."""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import io
import logging
import sys
import unittest

from funfuzz.util import fork_join

if sys.version_info.major == 2:
    import backports.tempfile as tempfile  # pylint: disable=import-error,no-name-in-module
    import logging_tz  # pylint: disable=import-error
    from pathlib2 import Path  # pylint: disable=import-error
else:
    from pathlib import Path  # pylint: disable=import-error
    import tempfile

FUNFUZZ_TEST_LOG = logging.getLogger(__name__)
FUNFUZZ_TEST_LOG.setLevel(logging.DEBUG)
LOG_HANDLER = logging.StreamHandler()
if sys.version_info.major == 2:
    LOG_FORMATTER = logging_tz.LocalFormatter(datefmt="[%Y-%m-%d %H:%M:%S %z]",
                                              fmt="%(asctime)s %(levelname)-8s %(message)s")
else:
    LOG_FORMATTER = logging.Formatter(datefmt="[%Y-%m-%d %H:%M:%S %z]",
                                      fmt="%(asctime)s %(levelname)-8s %(message)s")
LOG_HANDLER.setFormatter(LOG_FORMATTER)
FUNFUZZ_TEST_LOG.addHandler(LOG_HANDLER)
logging.getLogger("flake8").setLevel(logging.WARNING)


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

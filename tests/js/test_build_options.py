# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the build_options.py file."""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import logging
import sys
import unittest

from _pytest.monkeypatch import MonkeyPatch
import pytest

from funfuzz.js import build_options

if sys.version_info.major == 2:
    import logging_tz  # pylint: disable=import-error
    from pathlib2 import Path  # pylint: disable=import-error
else:
    from pathlib import Path  # pylint: disable=import-error

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


def mock_chance(i):
    """Overwrite the chance function to return True or False depending on a specific condition.

    Args:
        i (float): Intended probability between 0 < i < 1

    Returns:
        bool: True if i > 0, False otherwise.
    """
    return True if i > 0 else False


class BuildOptionsTests(unittest.TestCase):
    """"TestCase class for functions in build_options.py"""
    monkeypatch = MonkeyPatch()
    trees_location = Path.home() / "trees"

    # pylint: disable=no-member
    @pytest.mark.skipif(not (trees_location / "mozilla-central" / ".hg" / "hgrc").is_file(),
                        reason="requires a Mozilla Mercurial repository")
    def test_get_random_valid_repo(self):
        """Test that a valid repository can be obtained."""
        BuildOptionsTests.monkeypatch.setattr(build_options, "chance", mock_chance)
        assert build_options.get_random_valid_repo(self.trees_location) == self.trees_location / "mozilla-central"

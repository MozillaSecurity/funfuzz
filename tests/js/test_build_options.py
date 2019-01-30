# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the build_options.py file."""

import logging
from pathlib import Path

import pytest

from funfuzz.js import build_options

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.ERROR)

TREES_PATH = Path.home() / "trees"


def mock_chance(i):
    """Overwrite the chance function to return True or False depending on a specific condition.

    Args:
        i (float): Intended probability between 0 < i < 1

    Returns:
        bool: True if i > 0, False otherwise.
    """
    return i > 0


# pylint: disable=no-member
@pytest.mark.skipif(not (TREES_PATH / "mozilla-central" / ".hg" / "hgrc").is_file(),
                    reason="requires a Mozilla Mercurial repository")
def test_get_random_valid_repo(monkeypatch):
    """Test that a valid repository can be obtained.

    Args:
        monkeypatch (class): For monkeypatching some variables/functions
    """
    monkeypatch.setattr(build_options, "chance", mock_chance)
    assert build_options.get_random_valid_repo(TREES_PATH) == TREES_PATH / "mozilla-central"

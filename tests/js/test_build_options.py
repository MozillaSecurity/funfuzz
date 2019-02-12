# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the build_options.py file."""

import logging
from pathlib import Path
import random

import pytest

from funfuzz.js import build_options
from funfuzz.util.logging_helpers import get_logger

LOG_TEST_BUILD_OPTS = get_logger(__name__, level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.ERROR)

TREES_PATH = Path.home() / "trees"


def test_chance(monkeypatch):
    """Test that the chance function works as intended.

    Args:
        monkeypatch (class): Fixture from pytest for monkeypatching some variables/functions
    """
    monkeypatch.setattr(random, "random", lambda: 0)
    assert build_options.chance(0.6)
    assert build_options.chance(0.1)
    assert not build_options.chance(0)
    assert not build_options.chance(-0.2)


# pylint: disable=no-member
@pytest.mark.skipif(not (TREES_PATH / "mozilla-central" / ".hg" / "hgrc").is_file(),
                    reason="requires a Mozilla Mercurial repository")
def test_get_random_valid_repo(monkeypatch):
    """Test that a valid repository can be obtained.

    Args:
        monkeypatch (class): For monkeypatching some variables/functions
    """
    monkeypatch.setattr(random, "random", lambda: 0)
    assert build_options.get_random_valid_repo(TREES_PATH) == TREES_PATH / "mozilla-central"

# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the os_ops.py file."""

import logging
from pathlib import Path

from funfuzz.util import os_ops

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.ERROR)


def test_make_wtmp_dir(tmpdir):
    """Test that incrementally numbered wtmp directories can be created.

    Args:
        tmpdir (class): Fixture from pytest for creating a temporary directory
    """
    tmpdir = Path(tmpdir)

    wtmp_dir_1 = os_ops.make_wtmp_dir(tmpdir)
    assert wtmp_dir_1.is_dir()
    assert wtmp_dir_1.name.endswith("1")

    wtmp_dir_2 = os_ops.make_wtmp_dir(tmpdir)
    assert wtmp_dir_2.is_dir()
    assert wtmp_dir_2.name.endswith("2")

    wtmp_dir_3 = os_ops.make_wtmp_dir(tmpdir)
    assert wtmp_dir_3.is_dir()
    assert wtmp_dir_3.name.endswith("3")

    wtmp_dir_4 = os_ops.make_wtmp_dir(tmpdir)
    assert wtmp_dir_4.is_dir()
    assert wtmp_dir_4.name.endswith("4")

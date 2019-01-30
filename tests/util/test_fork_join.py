# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the fork_join.py file."""

import io
import logging
from pathlib import Path

from funfuzz.util import fork_join

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.ERROR)


def test_log_name(tmpdir):
    """Test that incrementally numbered wtmp directories can be created.

    Args:
        tmpdir (class): Fixture from pytest for creating a temporary directory
    """
    tmpdir = Path(tmpdir)
    log_path = tmpdir / "forkjoin-1-out.txt"

    with io.open(str(log_path), "w", encoding="utf-8", errors="replace") as f:
        f.writelines("test")

    assert fork_join.log_name(tmpdir, 1, "out") == str(log_path)

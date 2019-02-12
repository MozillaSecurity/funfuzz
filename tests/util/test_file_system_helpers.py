# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the file_system_helpers.py file."""

import io
import logging
from pathlib import Path
import platform
import stat

import pytest

from funfuzz import util

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.ERROR)


def test_delete_logs(tmpdir):
    """Test that delete_logs runs properly.

    Args:
        tmpdir (class): Fixture from pytest for creating a temporary directory
    """
    tmpdir = Path(tmpdir)

    wtmp_name = "w1"
    wtmp_name_out_txt = (tmpdir / f"{wtmp_name}-out.txt")
    wtmp_name_out_txt.touch()  # pylint: disable=no-member
    wtmp_name_out_binaryen_seed = (tmpdir / f"{wtmp_name}-out.binaryen-seed")
    wtmp_name_out_binaryen_seed.touch()  # pylint: disable=no-member
    wtmp_name_out_wasm = (tmpdir / f"{wtmp_name}-out.wasm")
    wtmp_name_out_wasm.touch()  # pylint: disable=no-member
    wtmp_name_out_wrapper = (tmpdir / f"{wtmp_name}-out.wrapper")
    wtmp_name_out_wrapper.touch()  # pylint: disable=no-member
    wtmp_name_err_txt = (tmpdir / f"{wtmp_name}-err.txt")
    wtmp_name_err_txt.touch()  # pylint: disable=no-member
    wtmp_name_wasm_err_txt = (tmpdir / f"{wtmp_name}-wasm-err.txt")
    wtmp_name_wasm_err_txt.touch()  # pylint: disable=no-member
    wtmp_name_wasm_out_txt = (tmpdir / f"{wtmp_name}-wasm-out.txt")
    wtmp_name_wasm_out_txt.touch()  # pylint: disable=no-member
    wtmp_name_wasm_summary_txt = (tmpdir / f"{wtmp_name}-wasm-summary.txt")
    wtmp_name_wasm_summary_txt.touch()  # pylint: disable=no-member
    wtmp_name_crash_txt = (tmpdir / f"{wtmp_name}-crash.txt")
    wtmp_name_crash_txt.touch()  # pylint: disable=no-member
    wtmp_name_vg_xml = (tmpdir / f"{wtmp_name}-vg.xml")
    wtmp_name_vg_xml.touch()  # pylint: disable=no-member
    wtmp_name_core_gz = (tmpdir / f"{wtmp_name}-core.gz")
    wtmp_name_core_gz.touch()  # pylint: disable=no-member

    util.file_system_helpers.delete_logs(tmpdir / wtmp_name)

    assert not wtmp_name_out_txt.is_file()
    assert not wtmp_name_out_binaryen_seed.is_file()
    assert not wtmp_name_out_wasm.is_file()
    assert not wtmp_name_out_wrapper.is_file()
    assert not wtmp_name_err_txt.is_file()
    assert not wtmp_name_wasm_err_txt.is_file()
    assert not wtmp_name_wasm_out_txt.is_file()
    assert not wtmp_name_wasm_summary_txt.is_file()
    assert not wtmp_name_crash_txt.is_file()
    assert not wtmp_name_vg_xml.is_file()
    assert not wtmp_name_core_gz.is_file()


@pytest.mark.skipif(platform.system() != "Windows", reason="Test only applies to read-only files on Windows")
def test_rm_tree_incl_readonly_files(tmpdir):
    """Test that directory trees with readonly files can be removed.

    Args:
        tmpdir (class): Fixture from pytest for creating a temporary directory
    """
    test_dir = Path(tmpdir) / "test_dir"
    read_only_dir = test_dir / "nested_read_only_dir"
    read_only_dir.mkdir(parents=True)

    test_file = read_only_dir / "test.txt"
    with io.open(test_file, "w", encoding="utf-8", errors="replace") as f:
        f.write("testing\n")

    Path.chmod(test_file, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    util.file_system_helpers.rm_tree_incl_readonly_files(test_dir)

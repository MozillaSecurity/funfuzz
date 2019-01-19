# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the file_system_helpers.py file."""

import logging
from pathlib import Path
import tempfile
import unittest

from funfuzz import util

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


class FileSystemHelpersTests(unittest.TestCase):
    """"TestCase class for functions in file_system_helpers.py"""
    @staticmethod
    def test_delete_logs():
        """Test that delete_logs runs properly."""
        with tempfile.TemporaryDirectory(suffix="_delete_logs_test") as tmp_dir:
            tmp_dir = Path(tmp_dir)

            wtmp_name = "w1"
            wtmp_name_out_txt = (tmp_dir / f"{wtmp_name}-out.txt")
            wtmp_name_out_txt.touch()  # pylint: disable=no-member
            wtmp_name_out_binaryen_seed = (tmp_dir / f"{wtmp_name}-out.binaryen-seed")
            wtmp_name_out_binaryen_seed.touch()  # pylint: disable=no-member
            wtmp_name_out_wasm = (tmp_dir / f"{wtmp_name}-out.wasm")
            wtmp_name_out_wasm.touch()  # pylint: disable=no-member
            wtmp_name_out_wrapper = (tmp_dir / f"{wtmp_name}-out.wrapper")
            wtmp_name_out_wrapper.touch()  # pylint: disable=no-member
            wtmp_name_err_txt = (tmp_dir / f"{wtmp_name}-err.txt")
            wtmp_name_err_txt.touch()  # pylint: disable=no-member
            wtmp_name_wasm_err_txt = (tmp_dir / f"{wtmp_name}-wasm-err.txt")
            wtmp_name_wasm_err_txt.touch()  # pylint: disable=no-member
            wtmp_name_wasm_out_txt = (tmp_dir / f"{wtmp_name}-wasm-out.txt")
            wtmp_name_wasm_out_txt.touch()  # pylint: disable=no-member
            wtmp_name_crash_txt = (tmp_dir / f"{wtmp_name}-crash.txt")
            wtmp_name_crash_txt.touch()  # pylint: disable=no-member
            wtmp_name_vg_xml = (tmp_dir / f"{wtmp_name}-vg.xml")
            wtmp_name_vg_xml.touch()  # pylint: disable=no-member
            wtmp_name_core_gz = (tmp_dir / f"{wtmp_name}-core.gz")
            wtmp_name_core_gz.touch()  # pylint: disable=no-member

            util.file_system_helpers.delete_logs(tmp_dir / wtmp_name)

            assert not wtmp_name_out_txt.is_file()
            assert not wtmp_name_out_binaryen_seed.is_file()
            assert not wtmp_name_out_wasm.is_file()
            assert not wtmp_name_out_wrapper.is_file()
            assert not wtmp_name_err_txt.is_file()
            assert not wtmp_name_wasm_err_txt.is_file()
            assert not wtmp_name_wasm_out_txt.is_file()
            assert not wtmp_name_crash_txt.is_file()
            assert not wtmp_name_vg_xml.is_file()
            assert not wtmp_name_core_gz.is_file()

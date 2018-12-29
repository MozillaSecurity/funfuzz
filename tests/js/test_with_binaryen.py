# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the with_binaryen.py file."""

import logging
from pathlib import Path
import subprocess

import pytest

from funfuzz.js import with_binaryen

from .test_compile_shell import CompileShellTests

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


class WithBinaryenTests(CompileShellTests):
    """"TestCase class for functions in with_binaryen.py"""
    wasm_file = Path(__file__).resolve().with_suffix(".wasm")
    wrapper_file = Path(__file__).resolve().with_suffix(".wrapper")

    @classmethod
    def teardown_class(cls):
        """Remove the binaryen-generated files on test completion."""
        cls.wasm_file.unlink()
        cls.wrapper_file.unlink()

    @staticmethod
    def test_ensure_binaryen():
        """Test that we are able to retrieve binaryen."""
        assert with_binaryen.ensure_binaryen(with_binaryen.BINARYEN_URL, with_binaryen.BINARYEN_VERSION)

    @staticmethod
    def test_wasmopt_run():
        """Test that we are able to run with wasm-opt from the binaryen repository."""
        assert with_binaryen.wasmopt_run(Path(__file__))

    @pytest.mark.slow
    def test_run_binaryen_generated(self):
        """Test that compiled SpiderMonkey builds are able to run binaryen-generated wasm files."""
        assert with_binaryen.wasmopt_run(Path(__file__))
        subprocess.run([self.test_shell_compile(), self.wrapper_file, self.wasm_file], check=True)

# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the with_binaryen.py file."""

import logging
from pathlib import Path
import platform
import subprocess

import pytest

from funfuzz.js import with_binaryen

from .test_compile_shell import test_shell_compile

FUNFUZZ_TEST_LOG = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.ERROR)

WASM_FILE = Path(__file__).resolve().with_suffix(".wasm")
WRAPPER_FILE = Path(__file__).resolve().with_suffix(".wrapper")


# See https://github.com/WebAssembly/binaryen/issues/1615
@pytest.mark.skipif("64" not in platform.machine(), reason="Only 64-bit binaryen binary makes sense to use now")
@pytest.fixture()
@pytest.mark.skipif(platform.system() != "Linux", reason="Only Linux binaryen binary is obtained for now")
def test_ensure_binaryen():
    """Test that we are able to retrieve binaryen."""
    assert with_binaryen.ensure_binaryen(with_binaryen.BINARYEN_URL, with_binaryen.BINARYEN_VERSION)


# See https://github.com/WebAssembly/binaryen/issues/1615
@pytest.mark.skipif("64" not in platform.machine(), reason="Only 64-bit binaryen binary makes sense to use now")
@pytest.fixture()
@pytest.mark.skipif(platform.system() != "Linux", reason="Only Linux binaryen binary is obtained for now")
def test_wasmopt_run(test_ensure_binaryen):  # pylint: disable=redefined-outer-name,unused-argument
    """Test that we are able to run with wasm-opt from the binaryen repository.

    Args:
        test_ensure_binaryen (class): Custom pytest fixture from this module
    """
    assert with_binaryen.wasmopt_run(Path(__file__))


# See https://github.com/WebAssembly/binaryen/issues/1615
@pytest.mark.skipif("64" not in platform.machine(), reason="Only 64-bit binaryen binary makes sense to use now")
@pytest.fixture()
@pytest.mark.skipif(platform.system() != "Linux", reason="Only Linux binaryen binary is obtained for now")
@pytest.mark.slow
def test_run_binaryen_generated(test_wasmopt_run):  # pylint: disable=redefined-outer-name,unused-argument
    """Test that compiled SpiderMonkey builds are able to run binaryen-generated wasm files.

    Args:
        test_wasmopt_run (class): Custom pytest fixture from this module
    """
    subprocess.run([test_shell_compile(), WRAPPER_FILE, WASM_FILE], check=True)


@pytest.mark.skipif(platform.system() != "Linux", reason="Only Linux binaryen binary is obtained for now")
@pytest.mark.slow
def test_teardown(test_run_binaryen_generated):  # pylint: disable=redefined-outer-name,unused-argument
    """Remove the binaryen-generated files on test completion after running the test_run_binaryen_generated test.

    Args:
        test_run_binaryen_generated (class): Custom pytest fixture from this module
    """
    WASM_FILE.unlink()
    WRAPPER_FILE.unlink()

# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Run seeds with binaryen to get a wasm file,
then run the shell with the translated wasm binary using a js file wrapper
"""

import io
import os
from pathlib import Path
import platform
import subprocess
import tarfile

import requests

from ..util import sm_compile_helpers

BINARYEN_VERSION = 52
BINARYEN_URL = (f"https://github.com/WebAssembly/binaryen/releases/download/version_{BINARYEN_VERSION}/"
                f"binaryen-version_{BINARYEN_VERSION}-{platform.uname()[4]}-linux.tar.gz")


def ensure_binaryen(url, version):
    """Download and use a compiled binaryen to generate WebAssembly files if it does not exist.

    Args:
        url (str): URL of the compressed binaryen binary package
        version (int): Version of the compressed binaryen binary package

    Returns:
        Path: Path of the extracted wasm-opt binary
    """
    shell_cache = sm_compile_helpers.ensure_cache_dir(Path.home())
    wasmopt_path = Path(shell_cache / f"binaryen-version_{version}" / "wasm-opt").resolve()

    if not wasmopt_path.is_file():
        with requests.get(url, allow_redirects=True, stream=True) as binaryen_gzip_request:
            with tarfile.open(fileobj=io.BytesIO(binaryen_gzip_request.content), mode="r:gz") as f:
                f.extractall(str(shell_cache.resolve()))
    return wasmopt_path


def wasmopt_run(seed):
    """Runs binaryen with the generated seed.

    Args:
        seed (Path): Generated jsfunfuzz file (acts as the seed for binaryen)

    Returns:
        bool: Returns True on successful wasm-opt execution, False otherwise
    """
    if platform.system() != "Linux":
        print("binaryen is only available on Linux systems")
        return False

    assert seed.is_file()
    seed_wrapper_output = seed.resolve().with_suffix(".wrapper")
    seed_wasm_output = seed.resolve().with_suffix(".wasm")
    subprocess.run([ensure_binaryen(BINARYEN_URL, BINARYEN_VERSION),
                    seed,
                    "--translate-to-fuzz",
                    "--output", seed_wasm_output,
                    f"--emit-js-wrapper={seed_wrapper_output}"], check=True)
    assert seed_wrapper_output.is_file()
    assert seed_wasm_output.is_file()

    return (seed_wrapper_output, seed_wasm_output)

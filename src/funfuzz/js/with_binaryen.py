# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Run seeds with binaryen to get a wasm file,
then run the shell with the translated wasm binary using a js file wrapper
"""

import io
from pathlib import Path
import platform
import subprocess
import tarfile
import threading
from time import sleep

import fasteners
import requests

from ..util import sm_compile_helpers
from ..util.file_system_helpers import safe_tar_extractall

BINARYEN_OS = platform.system().lower()
BINARYEN_ARCH = platform.machine()

if platform.system() == "Darwin":
    BINARYEN_OS = "apple-" + BINARYEN_OS
elif platform.system() == "Windows":
    BINARYEN_ARCH = "x86_64"

# If BINARYEN_VERSION number is bumped, we have to create new ARM64 VMs
BINARYEN_VERSION = 90
BINARYEN_URL = (f"https://github.com/WebAssembly/binaryen/releases/download/version_{BINARYEN_VERSION}/"
                f"binaryen-version_{BINARYEN_VERSION}-{BINARYEN_ARCH}-{BINARYEN_OS}.tar.gz")


def ensure_binaryen(url, version):
    """Download and use a compiled binaryen to generate WebAssembly files if it does not exist.

    Args:
        url (str): URL of the compressed binaryen binary package
        version (int): Version of the compressed binaryen binary package

    Returns:
        Path: Path of the extracted wasm-opt binary
    """
    shell_cache = sm_compile_helpers.ensure_cache_dir(Path.home())
    binaryen_path = shell_cache / f"binaryen-version_{version}"
    wasmopt_path = binaryen_path / ("wasm-opt" + (".exe" if platform.system() == "Windows" else ""))
    if wasmopt_path.is_file():
        return wasmopt_path

    # binaryen archives get extracted to a different name on Windows
    binaryen_path = shell_cache / (f"binaryen-version_{version}" +
                                   ("-x86_64-windows" if platform.system() == "Windows" else ""))
    wasmopt_path = binaryen_path / ("wasm-opt" + (".exe" if platform.system() == "Windows" else ""))

    sleep_time = 2
    t_lock = threading.Lock()
    with fasteners.try_lock(t_lock) as gotten:
        while not wasmopt_path.is_file():
            if gotten:
                with requests.get(url, allow_redirects=True, stream=True) as binaryen_gzip_request:
                    try:
                        with tarfile.open(fileobj=io.BytesIO(binaryen_gzip_request.content), mode="r:gz") as f:
                            safe_tar_extractall(f, str(shell_cache.resolve()))
                    except OSError:
                        print("binaryen tarfile threw an OSError")
                    break
            sleep(sleep_time)
            sleep_time *= 2

    if platform.system() == "Windows":
        assert binaryen_path.is_dir()
        new_win_binaryen_path = shell_cache / f"binaryen-version_{version}"
        binaryen_path.rename(new_win_binaryen_path)
        # Refresh binaryen_path and wasmopt_path
        binaryen_path = new_win_binaryen_path
        wasmopt_path = binaryen_path / ("wasm-opt" + (".exe" if platform.system() == "Windows" else ""))
    assert binaryen_path.is_dir()
    assert wasmopt_path.is_file()
    return wasmopt_path


def wasmopt_run(seed):
    """Runs binaryen with the generated seed.

    Args:
        seed (Path): Generated jsfunfuzz file (acts as the seed for binaryen)

    Returns:
        bool: Returns True on successful wasm-opt execution, False otherwise
    """
    assert platform.system() == "Linux"

    assert seed.is_file()
    seed_wrapper_output = seed.resolve().with_suffix(".wrapper")
    seed_wasm_output = seed.resolve().with_suffix(".wasm")

    sleep_time = 2
    t_lock = threading.Lock()
    with fasteners.try_lock(t_lock) as gotten:
        while True:
            if gotten:
                try:
                    # Wrapping this in str() seems necessary for Python 3.7.x and lower.
                    # See Python issue 31961
                    subprocess.run([str(ensure_binaryen(BINARYEN_URL, BINARYEN_VERSION)),
                                    str(seed),
                                    "--translate-to-fuzz",
                                    "--disable-simd",
                                    "--output", str(seed_wasm_output),
                                    f"--emit-js-wrapper={seed_wrapper_output}"], check=True)
                except (subprocess.CalledProcessError, OSError):
                    print("wasm-opt aborted with a CalledProcessError or OSError. Trying again after 1 minute...")
                    sleep(60)
                    # Wrapping this in str() seems necessary for Python 3.7.x and lower.
                    # See Python issue 31961
                    subprocess.run([str(ensure_binaryen(BINARYEN_URL, BINARYEN_VERSION)),
                                    str(seed),
                                    "--translate-to-fuzz",
                                    "--disable-simd",
                                    "--output", str(seed_wasm_output),
                                    f"--emit-js-wrapper={seed_wrapper_output}"], check=True)
                break
            sleep(sleep_time)
            sleep_time *= 2
    assert seed_wrapper_output.is_file()
    assert seed_wasm_output.is_file()

    return (seed_wrapper_output, seed_wasm_output)

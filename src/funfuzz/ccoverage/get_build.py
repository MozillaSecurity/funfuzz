# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Downloads coverage builds and other coverage utilities, such as grcov.
"""

import io
import logging
from pathlib import Path
import platform
import tarfile

import fuzzfetch
import requests

from ..js.inspect_shell import queryBuildConfiguration

RUN_COV_LOG = logging.getLogger("funfuzz")


def get_coverage_build(dirpath, rev):
    """Gets a coverage build from a specified server.

    Args:
        dirpath (Path): Directory in which build is to be downloaded in.
        rev (str): Mercurial hash of the required revision

    Returns:
        Path: Path to the js coverage build
    """
    RUN_COV_LOG.info("Obtaining coverage build zip file from TaskCluster, into %s", str(dirpath))

    extract_folder = dirpath / "cov-build"
    dirpath.mkdir(parents=True, exist_ok=True)  # Ensure this dir has been created

    # Use fuzzfetch to obtain build instead of wget
    fetcher, fetch_opts = fuzzfetch.Fetcher.from_args(
        [
            "--fuzzing",
            "--coverage",
            "--build", rev,
            "--name", "cov-build",
            "--out", str(dirpath),
            "--targets", "js",
        ],
        skip_dir_check=True,
    )
    extract_folder = Path(fetch_opts["out"])
    fetcher.extract_build(fetch_opts["targets"], extract_folder)

    RUN_COV_LOG.info("Coverage build zip file extracted to this folder: %s", extract_folder.resolve())

    js_cov_bin_name = f'js{".exe" if platform.system() == "Windows" else ""}'
    js_cov_bin = extract_folder / "dist" / "bin" / js_cov_bin_name

    Path.chmod(js_cov_bin, Path.stat(js_cov_bin).st_mode | 0o111)  # Ensure the js binary is executable
    assert js_cov_bin.is_file()

    # Check that the binary is non-debug.
    assert not queryBuildConfiguration(js_cov_bin, "debug")
    assert queryBuildConfiguration(js_cov_bin, "coverage")

    js_cov_fmconf = extract_folder / "dist" / "bin" / f"{js_cov_bin_name}.fuzzmanagerconf"
    assert js_cov_fmconf.is_file()

    # Check that a coverage build with *.gcno files are present
    js_cov_unified_gcno = extract_folder / "js" / "src" / "Unified_cpp_js_src0.gcno"
    assert js_cov_unified_gcno.is_file()

    return js_cov_bin


def get_grcov(dirpath, args):
    """Gets a grcov binary.

    Args:
        dirpath (Path): Directory in which build is to be downloaded in.
        args (class): Command line arguments.

    Raises:
        OSError: Raises if the current platform is neither Windows, Linux nor macOS

    Returns:
        Path: Path to the grcov binary file
    """
    append_os = "win" if platform.system() == "Windows" else ("osx" if platform.system() == "Darwin" else "linux")
    grcov_filename_with_ext = f"grcov-{append_os}-x86_64.tar.bz2"

    grcov_url = f"https://github.com/marco-c/grcov/releases/download/v{args.grcov_ver}/{grcov_filename_with_ext}"

    RUN_COV_LOG.info("Downloading grcov into %s from %s", str(dirpath), grcov_url)
    with requests.get(grcov_url, allow_redirects=True, stream=True) as grcov_request:
        RUN_COV_LOG.info("Extracting grcov tarball...")
        grcov_bin_folder = dirpath / "grcov-bin"
        grcov_bin_folder.mkdir(parents=True, exist_ok=True)  # Ensure this dir has been created for Python 3.5 reasons
        with tarfile.open(fileobj=io.BytesIO(grcov_request.content), mode="r:bz2") as f:
            f.extractall(str(grcov_bin_folder.resolve()))

    RUN_COV_LOG.info("grcov tarball extracted to this folder: %s", grcov_bin_folder.resolve())
    grcov_bin = grcov_bin_folder / f'grcov{".exe" if platform.system() == "Windows" else ""}'
    assert grcov_bin.is_file()

    return grcov_bin

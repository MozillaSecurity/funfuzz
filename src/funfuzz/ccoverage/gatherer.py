# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Gathers coverage data.
"""

import logging
import platform
import shutil
import subprocess

from ..bot import JS_SHELL_DEFAULT_TIMEOUT
from ..js.loop import get_path_prefix, many_timed_runs
from ..util import create_collector

RUN_COV_LOG = logging.getLogger("funfuzz")


def gather_coverage(dirpath, rev, run_cov_time, system_grcov=False):
    """Gathers coverage data.

    Args:
        dirpath (Path): Directory in which build is to be downloaded in.
        rev (str): Mercurial hash of the required revision

    Returns:
        Path: Path to the coverage results file
    """
    RUN_COV_LOG.info("Coverage build is being run in the following directory: %s", str(dirpath))
    bin_name = f'js{".exe" if platform.system() == "Windows" else ""}'
    cov_build_bin_path = dirpath / "cov-build" / "dist" / "bin" / bin_name
    assert cov_build_bin_path.is_file()
    path_prefix = get_path_prefix(cov_build_bin_path)
    loop_args = ["--compare-jit", "--random-flags",
                 str(JS_SHELL_DEFAULT_TIMEOUT), "KNOWNPATH", str(cov_build_bin_path), "--fuzzing-safe"]

    RUN_COV_LOG.info("Fuzzing a coverage build for %s seconds...", str(run_cov_time))
    many_timed_runs(run_cov_time, dirpath, loop_args, create_collector.make_collector(), True)
    RUN_COV_LOG.info("Finished fuzzing the coverage build")

    RUN_COV_LOG.info("Generating grcov data...")
    if system_grcov:
        grcov = str(shutil.which("grcov"))
    else:
        grcov = str(dirpath / "grcov-bin" / "grcov")
    RUN_COV_LOG.info("> using grcov at %s", grcov)

    cov_output_file = dirpath / "results_cov.json"
    RUN_COV_LOG.info("> writing coverage data to %s", cov_output_file)

    with cov_output_file.open("wb") as f:
        subprocess.run([grcov, str(dirpath / "cov-build"),
                        "-t", "coveralls+",
                        "--commit-sha", rev,
                        "--token", "NONE",
                        "--guess-directory-when-missing",
                        "--ignore-not-existing",
                        "-p", str(path_prefix),
                        "-s", str(dirpath / f"mozilla-central-{rev}")],
                        check=True,
                        stdout=f)
    RUN_COV_LOG.info("Finished generating grcov data")

    return cov_output_file

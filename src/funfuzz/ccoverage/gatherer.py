# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Gathers coverage data.
"""

import io
import logging
import platform
import subprocess

from ..bot import JS_SHELL_DEFAULT_TIMEOUT
from ..js.loop import many_timed_runs
from ..util import create_collector

RUN_COV_LOG = logging.getLogger("funfuzz")


def gather_coverage(dirpath, rev, run_cov_time):
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
    loop_args = ["--compare-jit", "--random-flags",
                 str(JS_SHELL_DEFAULT_TIMEOUT), "KNOWNPATH", str(cov_build_bin_path), "--fuzzing-safe"]

    RUN_COV_LOG.info("Fuzzing a coverage build for %s seconds...", str(run_cov_time))
    many_timed_runs(run_cov_time, dirpath, loop_args, create_collector.make_collector(), True)
    RUN_COV_LOG.info("Finished fuzzing the coverage build")

    RUN_COV_LOG.info("Generating grcov data...")
    cov_output = subprocess.run([str(dirpath / "grcov-bin" / "grcov"), str(dirpath),
                                 "-t", "coveralls+",
                                 "--commit-sha", rev,
                                 "--token", "NONE",
                                 "--guess-directory-when-missing",
                                 "-p", "/builds/worker/workspace/build/src/"],
                                check=True,
                                stdout=subprocess.PIPE).stdout.decode("utf-8", errors="replace")
    RUN_COV_LOG.info("Finished generating grcov data")

    RUN_COV_LOG.info("Writing grcov data to disk...")
    cov_output_file = dirpath / "results_cov.json"
    with io.open(str(cov_output_file), "w", encoding="utf-8", errors="replace") as f:
        f.write(cov_output)
    RUN_COV_LOG.info("Finished writing grcov data to disk")

    return cov_output_file

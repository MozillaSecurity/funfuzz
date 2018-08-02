# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Gathers coverage data.
"""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import configparser
import io
import logging
import platform
import sys

from ..bot import JS_SHELL_DEFAULT_TIMEOUT
from ..js.loop import many_timed_runs
from ..util import create_collector

if sys.version_info.major == 2:
    import logging_tz  # pylint: disable=import-error
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess

RUN_COV_LOG = logging.getLogger("run_ccoverage")
RUN_COV_LOG.setLevel(logging.INFO)
LOG_HANDLER = logging.StreamHandler()
if sys.version_info.major == 2:
    LOG_FORMATTER = logging_tz.LocalFormatter(datefmt="[%Y-%m-%d %H:%M:%S %z]",
                                              fmt="%(asctime)s %(name)s %(levelname)-8s %(message)s")
else:
    LOG_FORMATTER = logging.Formatter(datefmt="[%Y-%m-%d %H:%M:%S %z]",
                                      fmt="%(asctime)s %(name)s %(levelname)-8s %(message)s")
LOG_HANDLER.setFormatter(LOG_FORMATTER)
RUN_COV_LOG.addHandler(LOG_HANDLER)


def gather_coverage(dirpath):
    """Gathers coverage data.

    Args:
        dirpath (Path): Directory in which build is to be downloaded in.

    Returns:
        Path: Path to the coverage results file
    """
    RUN_COV_LOG.debug("Coverage build is being run in the following directory: %s", str(dirpath))
    bin_name = "js" + (".exe" if platform.system() == "Windows" else "")
    cov_build_bin_path = dirpath / "cov-build" / "dist" / "bin" / bin_name
    assert cov_build_bin_path.is_file()
    loop_args = ["--compare-jit", "--random-flags",
                 str(JS_SHELL_DEFAULT_TIMEOUT), "KNOWNPATH", str(cov_build_bin_path), "--fuzzing-safe"]

    cov_timeout = 85000  # 85,000 seconds is just under a day
    RUN_COV_LOG.info("Fuzzing a coverage build for %s seconds...", str(cov_timeout))
    many_timed_runs(cov_timeout, dirpath, loop_args, create_collector.make_collector(), True)
    RUN_COV_LOG.debug("Finished fuzzing the coverage build")

    fm_conf = configparser.SafeConfigParser()
    fm_conf.read(str(dirpath / "cov-build" / "dist" / "bin" / "js.fuzzmanagerconf"))
    RUN_COV_LOG.info("Generating grcov data...")
    cov_output = subprocess.run([str(dirpath / "grcov-bin" / "grcov"), str(dirpath),
                                 "-t", "coveralls+",
                                 "--commit-sha", fm_conf.get("Main", "product_version"),
                                 "--token", "NONE",
                                 "-p", "/srv/jenkins/jobs/mozilla-central-clone/workspace/"],
                                check=True,
                                stdout=subprocess.PIPE).stdout.decode("utf-8", errors="replace")
    RUN_COV_LOG.debug("Finished generating grcov data")

    RUN_COV_LOG.info("Writing grcov data to disk...")
    cov_output_file = dirpath / "results_cov.json"
    with io.open(str(cov_output_file), "w", encoding="utf-8", errors="replace") as f:
        f.write(cov_output)
    RUN_COV_LOG.debug("Finished writing grcov data to disk")

    return cov_output_file

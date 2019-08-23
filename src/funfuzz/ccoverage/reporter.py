# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Reports coverage build results to CovManager.
"""

from copy import deepcopy
import os

from CovReporter import CovReporter
from EC2Reporter import EC2Reporter

from ..util.logging_helpers import get_logger

LOG_COV_REPORTER = get_logger(__name__)


def disable_pool():
    """Disables coverage pool on collection completion."""
    spotman_env_var_name = "EC2SPOTMANAGER_POOLID"
    test_env = deepcopy(os.environ)
    if spotman_env_var_name in test_env:  # pragma: no cover
        pool_id = test_env[spotman_env_var_name]
        LOG_COV_REPORTER.info("About to disable EC2SpotManager pool ID: %s", pool_id)
        EC2Reporter.main(argv=["--disable", str(pool_id)])
        LOG_COV_REPORTER.info("Pool disabled!")
    else:
        LOG_COV_REPORTER.info("No pools were disabled, as the %s environment variable was not found",
                              spotman_env_var_name)


def report_coverage(cov_results):
    """Reports coverage results.

    Args:
        cov_results (Path): Path to the coverage .json results
    """
    LOG_COV_REPORTER.info("Submitting to CovManager...")
    assert not CovReporter.main(argv=["--repository", "mozilla-central",
                                      "--tool", "jsfunfuzz",
                                      "--submit", str(cov_results)])
    LOG_COV_REPORTER.info("Submission complete!")

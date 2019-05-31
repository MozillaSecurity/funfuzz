# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Reports coverage build results to CovManager.
"""

from copy import deepcopy
import logging
import os

from CovReporter import CovReporter
from EC2Reporter import EC2Reporter

RUN_COV_LOG = logging.getLogger("funfuzz")


def disable_pool():
    """Disables coverage pool on collection completion."""
    spotman_env_var_name = "EC2SPOTMANAGER_POOLID"
    test_env = deepcopy(os.environ)
    if spotman_env_var_name in test_env:  # pragma: no cover
        pool_id = test_env[spotman_env_var_name]
        RUN_COV_LOG.info("About to disable EC2SpotManager pool ID: %s", pool_id)
        EC2Reporter.main(argv=["--disable", str(pool_id)])
        RUN_COV_LOG.info("Pool disabled!")
    else:
        RUN_COV_LOG.info("No pools were disabled, as the %s environment variable was not found", spotman_env_var_name)


def report_coverage(cov_results):
    """Reports coverage results.

    Args:
        cov_results (Path): Path to the coverage .json results
    """
    RUN_COV_LOG.info("Submitting to CovManager...")
    assert not CovReporter.main(argv=["--repository", "mozilla-central",
                                      "--tool", "jsfunfuzz",
                                      "--submit", str(cov_results)])
    RUN_COV_LOG.info("Submission complete!")

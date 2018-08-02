# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Reports coverage build results to CovManager.
"""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import logging
import sys

from CovReporter import CovReporter

if sys.version_info.major == 2:
    import logging_tz  # pylint: disable=import-error

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

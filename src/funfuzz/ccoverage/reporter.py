# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Reports coverage build results to CovManager.
"""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import logging

from CovReporter import CovReporter

RUN_COV_LOG = logging.getLogger("funfuzz")


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

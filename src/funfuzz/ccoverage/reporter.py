# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Reports coverage build results to CovManager.
"""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import logging

# import os
# import platform
# import tarfile
# import sys
# import zipfile

# from CovReporter.CovReporter import CovReporter
# import requests

# if sys.version_info.major == 2:
#     import backports.tempfile as tempfile  # pylint: disable=import-error,no-name-in-module
#     from pathlib2 import Path
# else:
#     from pathlib import Path  # pylint: disable=import-error
#     import tempfile

RUN_COV_LOG = logging.getLogger("funfuzz")


def report_coverage(dirpath):
    """Reports coverage results.

    Args:
        dirpath (Path): Directory in which build is to be downloaded in.
    """
    RUN_COV_LOG.info(str(dirpath))
    # What happens if this is run in Travis? Does it still report to FM if .fuzzmanagerconf is not found?
    #                 USE CovReporter module
    #                 "--repository", "mozilla-central",
    #                 "--description", "funfuzz-test-20180427-ORSOMEOTHERDESC",
    #                 "--tool", "jsfunfuzz",
    #                 "--submit", "<SOMEFILENAME>",

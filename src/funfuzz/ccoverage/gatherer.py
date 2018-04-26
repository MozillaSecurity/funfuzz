# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Gathers coverage data.
"""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import logging
import sys

# import os
# import platform
# import tarfile
# import zipfile

# import requests

if sys.version_info.major == 2:
    import subprocess32 as subprocess  # pylint: disable=import-error
#     import backports.tempfile as tempfile  # pylint: disable=import-error,no-name-in-module
#     from pathlib2 import Path
else:
    import subprocess
#     from pathlib import Path  # pylint: disable=import-error
#     import tempfile

RUN_COV_LOG = logging.getLogger("funfuzz")


def gather_coverage(dirpath):
    """Gathers coverage data.

    Args:
        dirpath (Path): Directory in which build is to be downloaded in.
    """
    RUN_COV_LOG.info(str(dirpath))
    # 25 - 100 runs
    # For testing run for shorter time. Use Docker.
    # Run for 23.9 hours for things to shut down
    # programmatically in userdata/Docker get this to shut down the EC2SpotManager pool
    # same mini-timeout as regular bot.py

    # GCOV_PREFIX_STRIP=13
    # GCOV_PREFIX=~/<some dir>/buildcovjs/
    #   buildcovjs/dist/bin/js --fuzzing-safe --no-threads --ion-eager
    subprocess.run(["ls"], check=True)

    # ./grcov
    # ~/<some dir>/buildcovjs/
    # -t coveralls+
    # --commit-sha d2d518b1f873
    # --token NONE
    #   -p /srv/jenkins/jobs/mozilla-central-clone/workspace/
    # > cov.json
    subprocess.run(["ls"], check=True)

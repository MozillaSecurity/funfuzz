# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""A class to create a filesystem-based lock while in scope. The lock directory will be deleted after the lock is
released.
"""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

from builtins import object
import logging
import sys

if sys.version_info.major == 2:
    import logging_tz  # pylint: disable=import-error

FUNFUZZ_LOG = logging.getLogger("funfuzz")
FUNFUZZ_LOG.setLevel(logging.DEBUG)
LOG_HANDLER = logging.StreamHandler()
if sys.version_info.major == 2:
    LOG_FORMATTER = logging_tz.LocalFormatter(datefmt="[%Y-%m-%d %H:%M:%S%z]",
                                              fmt="%(asctime)s %(name)s %(levelname)-8s %(message)s")
else:
    LOG_FORMATTER = logging.Formatter(datefmt="[%Y-%m-%d %H:%M:%S%z]",
                                      fmt="%(asctime)s %(name)s %(levelname)-8s %(message)s")
LOG_HANDLER.setFormatter(LOG_FORMATTER)
FUNFUZZ_LOG.addHandler(LOG_HANDLER)


class LockDir(object):
    """Create a filesystem-based lock while in scope.

    Use:
        with LockDir(path):
            # No other code is concurrently using LockDir(path)

    Args:
        directory (str): Lock directory name
    """

    def __init__(self, directory):
        self.directory = directory

    def __enter__(self):
        try:
            self.directory.mkdir()
        except OSError:
            FUNFUZZ_LOG.error("Lock directory exists: %s", self.directory)
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.directory.rmdir()

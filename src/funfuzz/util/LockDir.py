# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""A class to create a filesystem-based lock while in scope. The lock directory will be deleted after the lock is
released.
"""

from __future__ import absolute_import, print_function

import os


class LockDir(object):  # pylint: disable=missing-param-doc,missing-type-doc,too-few-public-methods
    """Create a filesystem-based lock while in scope.

    Use:
        with LockDir(path):
            # No other code is concurrently using LockDir(path)
    """

    def __init__(self, directory):
        self.directory = directory

    def __enter__(self):
        try:
            os.mkdir(self.directory)
        except OSError:
            print("Lock file exists: %s" % self.directory)
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.rmdir(self.directory)

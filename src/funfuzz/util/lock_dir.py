# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""A class to create a filesystem-based lock while in scope. The lock directory will be deleted after the lock is
released.
"""


class LockDir:
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
            print(f"Lock directory exists: {self.directory}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.directory.rmdir()

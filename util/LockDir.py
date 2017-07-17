#!/usr/bin/env python
# coding=utf-8
# pylint: disable=invalid-name,missing-docstring,old-style-class,too-few-public-methods
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import absolute_import, print_function

import os


class LockDir():
    """
    Create a filesystem-based lock while in scope.

    Use:
        with LockDir(path):
            # No other code is concurrently using LockDir(path)
    """

    def __init__(self, d):
        self.d = d

    def __enter__(self):
        try:
            os.mkdir(self.d)
        except OSError:
            print("Lock file exists: %s" % self.d)
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.rmdir(self.d)

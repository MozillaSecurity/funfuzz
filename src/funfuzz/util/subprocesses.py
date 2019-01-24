# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Miscellaneous helper functions.
"""

verbose = False  # pylint: disable=invalid-name


def vdump(inp):  # pylint: disable=missing-param-doc,missing-type-doc
    """Append the word "DEBUG" to any verbose output."""
    if verbose:
        print(f"DEBUG - {inp}")

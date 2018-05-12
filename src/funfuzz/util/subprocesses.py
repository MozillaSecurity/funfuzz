# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Miscellaneous helper functions.
"""

from __future__ import absolute_import, print_function  # isort:skip

import errno
import os
import platform
import shutil
import stat

verbose = False  # pylint: disable=invalid-name


def rm_tree_incl_readonly(dir_tree):
    """Remove a directory tree including all read-only files.

    Args:
        dir_tree (Path): Directory tree of files to be removed
    """
    shutil.rmtree(str(dir_tree), onerror=handle_rm_readonly if platform.system() == "Windows" else None)


# This test needs updates for the move to pathlib, and needs to move to pytest
# def test_rm_tree_incl_readonly():  # pylint: disable=invalid-name
#     """Run this function in the same directory as subprocesses to test."""
#     test_dir = "test_rm_tree_incl_readonly"
#     os.mkdir(test_dir)
#     read_only_dir = os.path.join(test_dir, "nestedReadOnlyDir")
#     os.mkdir(read_only_dir)
#     filename = os.path.join(read_only_dir, "test.txt")
#     with open(filename, "w") as f:
#         f.write("testing\n")

#     os.chmod(filename, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
#     os.chmod(read_only_dir, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

#     rm_tree_incl_readonly(test_dir)  # Should pass here


def handle_rm_readonly(func, path, exc):
    """Handle read-only files. Adapted from http://stackoverflow.com/q/1213706 and some docs below adapted from
    Python 2.7 official docs.

    Args:
        func (function): Function which raised the exception
        path (str): Path name passed to function
        exc (exception): Exception information returned by sys.exc_info()

    Raises:
        OSError: Raised if the read-only files are unable to be handled
    """
    if func in (os.rmdir, os.remove) and exc[1].errno == errno.EACCES:
        if os.name == "posix":
            # Ensure parent directory is also writeable.
            pardir = os.path.abspath(os.path.join(path, os.path.pardir))
            if not os.access(pardir, os.W_OK):
                os.chmod(pardir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        elif os.name == "nt":
            os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 0777
        func(path)
    else:
        raise OSError("Unable to handle read-only files.")


def vdump(inp):  # pylint: disable=missing-param-doc,missing-type-doc
    """Append the word "DEBUG" to any verbose output."""
    if verbose:
        print("DEBUG - %s" % inp)

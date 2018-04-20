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
import subprocess
import sys

from shellescape import quote

verbose = False  # pylint: disable=invalid-name


# pylint: disable=invalid-name,missing-param-doc,missing-raises-doc,missing-return-doc,missing-return-type-doc
# pylint: disable=missing-type-doc,too-complex,too-many-arguments,too-many-branches,too-many-statements
def captureStdout(inputCmd, ignoreStderr=False, combineStderr=False, ignoreExitCode=False, currWorkingDir=None,
                  env="NOTSET", verbosity=False):
    """Capture standard output, return the output as a string, along with the return value."""
    currWorkingDir = str(currWorkingDir) or (
        os.getcwdu() if sys.version_info.major == 2 else os.getcwd())  # pylint: disable=no-member
    if env == "NOTSET":
        vdump(" ".join(quote(x) for x in inputCmd))
        env = os.environ
    else:
        # There is no way yet to only print the environment variables that were added by the harness
        # We could dump all of os.environ but it is too much verbose output.
        vdump("ENV_VARIABLES_WERE_ADDED_HERE " + " ".join(quote(x) for x in inputCmd))
    cmd = []
    for el in inputCmd:
        if el.startswith('"') and el.endswith('"'):
            cmd.append(str(el[1:-1]))
        else:
            cmd.append(str(el))
    assert cmd != []
    try:
        p = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if combineStderr else subprocess.PIPE,
            cwd=currWorkingDir,
            env=env)
        (stdout, stderr) = p.communicate()
    except OSError as e:
        raise Exception(repr(e.strerror) + " error calling: " + " ".join(quote(x) for x in cmd))
    if p.returncode != 0:
        oomErrorOutput = stdout if combineStderr else stderr
        if (platform.system() == "Linux" or platform.system() == "Darwin") and oomErrorOutput:
            if "internal compiler error: Killed (program cc1plus)" in oomErrorOutput:
                raise Exception("GCC running out of memory")
            elif "error: unable to execute command: Killed" in oomErrorOutput:
                raise Exception("Clang running out of memory")
        if not ignoreExitCode:
            # Potential problem area: Note that having a non-zero exit code does not mean that the
            # operation did not succeed, for example when compiling a shell. A non-zero exit code
            # can appear even though a shell compiled successfully.
            # Pymake in builds earlier than revision 232553f741a0 did not support the "-s" option.
            if "no such option: -s" not in stdout:
                print("Nonzero exit code from: ")
                print("  %s" % " ".join(quote(x) for x in cmd))
                print("stdout is:")
                print(stdout)
            if stderr is not None:
                print("stderr is:")
                print(stderr)
            # Pymake in builds earlier than revision 232553f741a0 did not support the "-s" option.
            if "hg pull: option --rebase not recognized" not in stdout and "no such option: -s" not in stdout:
                if platform.system() == "Windows" and stderr and "Permission denied" in stderr and \
                        "configure: error: installation or configuration problem: " + \
                        "C++ compiler cannot create executables." in stderr:
                    raise Exception("Windows conftest.exe configuration permission problem")
                else:
                    raise Exception("Nonzero exit code")
    if not combineStderr and not ignoreStderr and stderr:
        # Ignore hg color mode throwing an error in console on Windows platforms.
        if not (platform.system() == "Windows" and "warning: failed to set color mode to win32" in stderr):
            print("Unexpected output on stderr from: ")
            print("  %s" % " ".join(quote(x) for x in cmd))
            print("%s %s" % (stdout, stderr))
            raise Exception("Unexpected output on stderr")
    if stderr and ignoreStderr and stderr and p.returncode != 0:
        # During configure, there will always be stderr. Sometimes this stderr causes configure to
        # stop the entire script, especially on Windows.
        print("Return code not zero, and unexpected output on stderr from: ")
        print("  %s" % " ".join(quote(x) for x in cmd))
        print("%s %s" % (stdout, stderr))
        raise Exception("Return code not zero, and unexpected output on stderr")
    if verbose or verbosity:
        print(stdout)
        if stderr is not None:
            print(stderr)
    return stdout.rstrip(), p.returncode


def getAbsPathForAdjacentFile(filename):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Get the absolute path of a particular file, given its base directory and filename."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


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


def normExpUserPath(p):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    return os.path.normpath(os.path.expanduser(p))


def vdump(inp):  # pylint: disable=missing-param-doc,missing-type-doc
    """Append the word "DEBUG" to any verbose output."""
    if verbose:
        print("DEBUG - %s" % inp)

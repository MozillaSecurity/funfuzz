#!/usr/bin/env python
# coding=utf-8
# pylint: disable=invalid-name,missing-docstring
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import absolute_import, division

import collections
import logging
import os
import shutil
import sys
import tempfile
import unittest

import funfuzz  # noqa pylint: disable=wrong-import-position

funfuzz_log = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


# python 3 has unlimited precision integers
# restrict tests to 64-bit
if not hasattr(sys, "maxint"):
    sys.maxint = (1 << 64) - 1


class TestCase(unittest.TestCase):

    def setUp(self):
        self.tmpd = tempfile.mkdtemp(prefix='funfuzztest')
        self.cwd = os.getcwd()
        os.chdir(self.tmpd)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmpd)

    if sys.version_info.major == 2:

        def assertRegex(self, *args, **kwds):  # pylint: disable=arguments-differ
            # pylint: disable=missing-return-doc,missing-return-type-doc
            return self.assertRegexpMatches(*args, **kwds)  # pylint: disable=deprecated-method

        def assertRaisesRegex(self, *args, **kwds):  # pylint: disable=arguments-differ
            # pylint: disable=missing-return-doc,missing-return-type-doc
            return self.assertRaisesRegexp(*args, **kwds)  # pylint: disable=deprecated-method

    if sys.version_info[:2] < (3, 4):
        #
        # polyfill adapted from https://github.com/python/cpython/blob/3.6/Lib/unittest/case.py
        #
        # This method is licensed as follows:
        #
        # Copyright (c) 1999-2003 Steve Purcell
        # Copyright (c) 2003-2010 Python Software Foundation
        # This module is free software, and you may redistribute it and/or modify
        # it under the same terms as Python itself, so long as this copyright message
        # and disclaimer are retained in their original form.
        #
        # IN NO EVENT SHALL THE AUTHOR BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT,
        # SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES ARISING OUT OF THE USE OF
        # THIS CODE, EVEN IF THE AUTHOR HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH
        # DAMAGE.
        #
        # THE AUTHOR SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT
        # LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
        # PARTICULAR PURPOSE.  THE CODE PROVIDED HEREUNDER IS ON AN "AS IS" BASIS,
        # AND THERE IS NO OBLIGATION WHATSOEVER TO PROVIDE MAINTENANCE,
        # SUPPORT, UPDATES, ENHANCEMENTS, OR MODIFICATIONS.

        def assertLogs(self, logger=None, level=None):  # pylint: disable=missing-return-doc,missing-return-type-doc

            _LoggingWatcher = collections.namedtuple("_LoggingWatcher", ["records", "output"])

            class _CapturingHandler(logging.Handler):
                def __init__(self):
                    logging.Handler.__init__(self)
                    self.watcher = _LoggingWatcher([], [])

                def emit(self, record):
                    self.watcher.records.append(record)
                    self.watcher.output.append(self.format(record))

            class _AssertLogsContext(object):  # pylint: disable=too-few-public-methods
                LOGGING_FORMAT = "%(levelname)s:%(name)s:%(message)s"

                def __init__(self, test_case, logger_name, level):
                    self.test_case = test_case
                    self.logger = None
                    self.logger_name = logger_name
                    self.level = getattr(logging, level) if level else logging.INFO
                    self.msg = None
                    self.old = None
                    self.watcher = None

                def __enter__(self):  # pylint: disable=missing-return-doc,missing-return-type-doc
                    if isinstance(self.logger_name, logging.Logger):
                        self.logger = self.logger_name
                    else:
                        self.logger = logging.getLogger(self.logger_name)
                    handler = _CapturingHandler()
                    handler.setFormatter(logging.Formatter(self.LOGGING_FORMAT))
                    self.watcher = handler.watcher
                    self.old = (self.logger.handlers[:], self.logger.propagate, self.logger.level)
                    self.logger.handlers = [handler]
                    self.logger.setLevel(self.level)
                    self.logger.propagate = False
                    return handler.watcher

                def __exit__(self, exc_type, exc_value, tb):  # pylint: disable=missing-return-doc
                    # pylint: disable=missing-return-type-doc
                    self.logger.handlers, self.logger.propagate = self.old[:2]
                    self.logger.setLevel(self.old[2])
                    if exc_type is not None:
                        return False
                    self.test_case.assertGreater(
                        len(self.watcher.records), 0,
                        "no logs of level %s or higher triggered on %s" % (
                            logging.getLevelName(self.level), self.logger.name))

            return _AssertLogsContext(self, logger, level)


class CompileTests(TestCase):
    def test_compile_shell_A_dbg(self):  # pylint: disable=no-self-use
        """Test compilation of a debug shell with determinism, valgrind and OOM breakpoint support."""
        self.assertEqual(os.path.isdir(os.path.join(os.path.expanduser("~"), "trees", "mozilla-central")), True)
        # Remember to update the expected binary filename
        build_opts = ("--enable-debug --disable-optimize --enable-more-deterministic "
                      "--build-with-valgrind --enable-oom-breakpoint")
        # Change the repository location by uncommenting this line and specifying the right one
        # "-R ~/trees/mozilla-central/")
        build_opts_processed = funfuzz.js.build_options.parseShellOptions(build_opts)

        hg_hash_of_default = funfuzz.util.hg_helpers.getRepoHashAndId(build_opts_processed.repoDir)[0]

        fz = funfuzz.js.compile_shell.CompiledShell()
        fz.setShellNameWithoutExt(build_opts_processed, hg_hash_of_default)
        fz.setHgHash(hg_hash_of_default)
        fz.set_build_opts(build_opts_processed)

        result = fz.run(["-b", build_opts])
        self.assertEqual(result, 0)
        self.assertEqual(os.path.isfile(os.path.join(
            os.path.expanduser("~"), "shell-cache",
            "js-dbg-optDisabled-64-dm-vg-oombp-linux-" + hg_hash_of_default)), 0)

    def test_compile_shell_B_opt(self):  # pylint: disable=no-self-use
        """Test compilation of an opt shell with both profiling and Intl support disabled."""
        # Remember to update the expected binary filename
        build_opts = ("--disable-debug --disable-profiling --without-intl-api")
        # Change the repository location by uncommenting this line and specifying the right one
        # "-R ~/trees/mozilla-central/")
        build_opts_processed = funfuzz.js.build_options.parseShellOptions(build_opts)

        hg_hash_of_default = funfuzz.util.hg_helpers.getRepoHashAndId(build_opts_processed.repoDir)[0]

        fz = funfuzz.js.compile_shell.CompiledShell()
        fz.setShellNameWithoutExt(build_opts_processed, hg_hash_of_default)
        fz.setHgHash(hg_hash_of_default)
        fz.set_build_opts(build_opts_processed)

        # This set of builds should also have the following: 32-bit with ARM, with asan, and with clang
        result = fz.run(["-b", build_opts])
        self.assertEqual(result, 0)
        self.assertEqual(os.path.isfile(os.path.join(
            os.path.expanduser("~"), "shell-cache",
            "js-profDisabled-64-intlDisabled-linux-" + hg_hash_of_default)), 0)

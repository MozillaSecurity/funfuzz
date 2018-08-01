# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Runs coverage builds for a set amount of time and reports it to CovManager

"""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

import argparse
import logging
import platform
import sys

from .ccoverage import gatherer
from .ccoverage import get_build
from .ccoverage import reporter

if sys.version_info.major == 2:
    import backports.tempfile as tempfile  # pylint: disable=import-error,no-name-in-module
    import logging_tz  # pylint: disable=import-error
    from pathlib2 import Path  # pylint: disable=import-error
else:
    from pathlib import Path  # pylint: disable=import-error
    import tempfile

RUN_COV_LOG = logging.getLogger("run_ccoverage")
RUN_COV_LOG.setLevel(logging.DEBUG)
LOG_HANDLER = logging.StreamHandler()
if sys.version_info.major == 2:
    LOG_FORMATTER = logging_tz.LocalFormatter(datefmt="[%Y-%m-%d %H:%M:%S%z]",
                                              fmt="%(asctime)s %(name)s %(levelname)-8s %(message)s")
else:
    LOG_FORMATTER = logging.Formatter(datefmt="[%Y-%m-%d %H:%M:%S%z]",
                                      fmt="%(asctime)s %(name)s %(levelname)-8s %(message)s")
LOG_HANDLER.setFormatter(LOG_FORMATTER)
RUN_COV_LOG.addHandler(LOG_HANDLER)


def parse_args(args=None):
    """Parses arguments from the command line.

    Args:
        args (None): Argument parameters, defaults to None.

    Returns:
        class: Namespace of argparse parameters.
    """
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--report", action="store_true", help="Report results to FuzzManager")
    arg_parser.add_argument("--grcov_ver",
                            default="0.1.37",
                            help='Set the version of grcov to use. Defaults to "%(default)s".')
    arg_parser.add_argument("--url",
                            required=True,
                            help="URL to the downloadable js binary with coverage support")
    arg_parser.add_argument("-v", "--verbose", action="store_true", help="Show more information for debugging")
    return arg_parser.parse_args(args)


def main(argparse_args=None):
    """Gets a coverage build, run it for a set amount of time then report it.

    Args:
        argparse_args (None): Argument parameters, defaults to None.
    """
    if platform.system() != "Linux":
        sys.exit("Coverage mode must be run on Linux.")
    args = parse_args(argparse_args)
    logging.basicConfig(datefmt="%Y-%m-%d %H:%M:%S",
                        format="%(asctime)s %(levelname)-8s %(message)s",
                        level=logging.DEBUG if args.verbose else logging.INFO)
    logging.getLogger("flake8").setLevel(logging.WARNING)

    with tempfile.TemporaryDirectory(suffix="funfuzzcov") as dirpath:
        dirpath = Path(dirpath)

        get_build.get_coverage_build(dirpath, args)
        get_build.get_grcov(dirpath, args)
        cov_result_file = gatherer.gather_coverage(dirpath)
        if args.report:
            reporter.report_coverage(cov_result_file)


if __name__ == "__main__":
    main()

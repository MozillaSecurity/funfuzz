# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Runs coverage builds for a set amount of time and reports it to CovManager

"""

from __future__ import absolute_import, unicode_literals  # isort:skip

import argparse
import logging
import platform
import sys

from funfuzz import ccoverage

if sys.version_info.major == 2:
    import backports.tempfile as tempfile  # pylint: disable=import-error,no-name-in-module
    from pathlib2 import Path
else:
    from pathlib import Path  # pylint: disable=import-error
    import tempfile

RUN_COV_LOG = logging.getLogger("funfuzz")


def parse_args(args=None):
    """Parses arguments from the command line.

    Args:
        args (None): Argument parameters, defaults to None.

    Returns:
        class: Namespace of argparse parameters.
    """
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--report", action="store_true", help="Report results to FuzzManager")
    # arg_parser.add_argument("-c", "--ccov_cmd_with_flags",
    #                         required=True,
    #                         help="Parameters to pass to many_timed_run")
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
        sys.exit("Coverage mode must be run on Linux for now.")
    args = parse_args(argparse_args)
    logging.basicConfig(datefmt="%Y-%m-%d %H:%M:%S",
                        format="%(asctime)s %(levelname)-8s %(message)s",
                        level=logging.DEBUG if args.verbose else logging.INFO)
    logging.getLogger("flake8").setLevel(logging.WARNING)

    with tempfile.TemporaryDirectory(suffix="funfuzzcov") as dirpath:
        dirpath = Path(dirpath)

        ccoverage.get_build.get_coverage_build(dirpath, args)
        ccoverage.get_build.get_grcov(dirpath, args)
        ccoverage.gatherer.gather_coverage(dirpath)
        if args.report:
            ccoverage.reporter.report_coverage(dirpath)


if __name__ == "__main__":
    main()

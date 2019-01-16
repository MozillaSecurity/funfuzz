# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Runs coverage builds for a set amount of time and reports it to CovManager

"""

import argparse
import logging
from pathlib import Path
import platform
import sys
import tempfile

from .ccoverage import gatherer
from .ccoverage import get_build
from .ccoverage import reporter
from .util.logging_helpers import get_logger


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
                            default="0.2.3",
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
    log_run_cov = get_logger(__name__, level=logging.DEBUG if args.verbose else logging.INFO)

    with tempfile.TemporaryDirectory(suffix="funfuzzcov") as dirpath:
        dirpath = Path(dirpath)

        log_run_cov.debug("Starting to get the coverage build")
        get_build.get_coverage_build(dirpath, args)
        log_run_cov.debug("Coverage build obtained")

        log_run_cov.debug("Starting to get the grcov binary")
        get_build.get_grcov(dirpath, args)
        log_run_cov.debug("grcov binary obtained")

        log_run_cov.debug("Starting to gather coverage")
        cov_result_file = gatherer.gather_coverage(dirpath)
        log_run_cov.debug("Finished gathering coverage")

        if args.report:
            log_run_cov.debug("Starting to report coverage")
            reporter.report_coverage(cov_result_file)
            log_run_cov.debug("Finished reporting coverage")

        log_run_cov.debug("Starting to disable EC2 pool")
        reporter.disable_pool()
        log_run_cov.debug("Finished disabling EC2 pool")


if __name__ == "__main__":
    main()

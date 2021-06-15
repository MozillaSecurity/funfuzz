# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Runs coverage builds for a set amount of time and reports it to CovManager

"""

import argparse
import logging
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile

import requests

from .ccoverage import gatherer
from .ccoverage import get_build
from .ccoverage import reporter

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
    arg_parser.add_argument("--grcov_ver",
                            default="system",
                            help='Set the version of grcov to use. Defaults to "%(default)s".')
    arg_parser.add_argument("--url",
                            help="URL to the downloadable js binary with coverage support")
    arg_parser.add_argument("--target-time", type=int, default=85000, help="Coverage gathering runtime")
    arg_parser.add_argument("-v", "--verbose", action="store_true", help="Show more information for debugging")
    return arg_parser.parse_args(args)


def main(argparse_args=None):
    """Gets a coverage build, run it for a set amount of time then report it.

    Args:
        argparse_args (None): Argument parameters, defaults to None.

    Raises:
        ValueError: Raises if --url value is specified. Retained for backward compatibility purposes
    """
    if platform.system() != "Linux":
        sys.exit("Coverage mode must be run on Linux.")
    args = parse_args(argparse_args)
    if args.url:
        raise ValueError("Now using fuzzfetch so the --url value is no longer relevant")
    logging.basicConfig(datefmt="%Y-%m-%d %H:%M:%S",
                        format="%(asctime)s %(levelname)-8s %(message)s",
                        level=logging.DEBUG if args.verbose else logging.INFO)
    logging.getLogger("flake8").setLevel(logging.ERROR)

    with tempfile.TemporaryDirectory(suffix="funfuzzcov") as dirpath:
        dirpath = Path(dirpath)

        cov_revision_request = requests.get("https://community-tc.services.mozilla.com/api/index/v1/task/project.fuzzing.coverage-revision.latest/artifacts/public/coverage-revision.txt")
        cov_revision_str = cov_revision_request.content.rstrip().decode("utf-8", errors="replace")

        get_build.get_coverage_build(dirpath, cov_revision_str)
        if args.grcov_ver != "system":
            get_build.get_grcov(dirpath, args)
        cov_result_file = gatherer.gather_coverage(dirpath, cov_revision_str, args.target_time, args.grcov_ver == "system")
        if args.report:
            reporter.report_coverage(cov_result_file)
        if "COVERAGE_ARTIFACT_PATH" in os.environ:
            coverage_artifact_path = Path(os.environ["COVERAGE_ARTIFACT_PATH"])
            if coverage_artifact_path.is_dir():
                shutil.copy2(str(cov_result_file), str(coverage_artifact_path / cov_result_file.name))
            else:
                RUN_COV_LOG.warning("COVERAGE_ARTIFACT_PATH=%s given, but is not a directory!", coverage_artifact_path)
        reporter.disable_pool()


if __name__ == "__main__":
    main()

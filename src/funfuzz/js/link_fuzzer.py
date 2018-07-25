# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Concatenate js files to create jsfunfuzz.
"""

from __future__ import absolute_import

import io
import sys

if sys.version_info.major == 2:
    from pathlib2 import Path  # pylint: disable=import-error
else:
    from pathlib import Path  # pylint: disable=import-error


def link_fuzzer(target_path, prologue=""):
    """Links files together to create the full jsfunfuzz file.

    Args:
        target_path (Path): Target file with full path, to be created
        prologue (str): Contents to be prepended to the target file
    """
    base_dir = Path(__file__).parent

    with io.open(str(target_path), "w", encoding="utf-8", errors="replace") as f:  # Create the full jsfunfuzz file
        if prologue:
            f.write(prologue)

        for entry in (base_dir / "files_to_link.txt").read_text().split():  # pylint: disable=no-member
            entry = entry.rstrip()
            if entry and not entry.startswith("#"):
                file_path = base_dir / Path(entry)
                file_name = "\n\n// %s\n\n" % str(file_path).split("funfuzz", 1)[1][1:]
                # For dual Python 2 and 3 compatibility
                if isinstance(file_name, b"".__class__):
                    file_name = file_name.decode("utf-8", errors="replace")
                f.write(file_name)
                f.write(file_path.read_text())  # pylint: disable=no-member

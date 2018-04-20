# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Functions to concatenate files, with one specially for js files.
"""

from __future__ import absolute_import, print_function  # isort:skip

import os


def link_js(target_fn, file_list_fn, source_base, prologue="", module_dirs=None):
    # pylint: disable=missing-docstring
    module_dirs = module_dirs or []
    with open(target_fn, "w") as target:
        target.write(prologue)

        # Add files listed in file_list_fn
        with open(file_list_fn) as file_list:
            for source_fn in file_list:
                source_fn = source_fn.replace("/", os.path.sep).strip()
                if source_fn and source_fn[0] != "#":
                    add_contents(os.path.join(source_base, source_fn), target)

        # Add all *.js files in module_dirs
        for module_base in module_dirs:
            for module_fn in os.listdir(module_base):
                if module_fn.endswith(".js"):
                    add_contents(os.path.join(module_base, module_fn), target)


def add_contents(source_fn, target):  # pylint: disable=missing-docstring
    target.write("\n\n// " + source_fn + "\n\n")
    with open(source_fn) as source:
        for line in source:
            target.write(line)

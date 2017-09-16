#!/usr/bin/env python
# coding=utf-8
# pylint: disable=invalid-name,missing-docstring
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import absolute_import, print_function

import os


def linkJS(target_fn, file_list_fn, source_base, prologue="", module_dirs=None):
    module_dirs = module_dirs or []
    with open(target_fn, "wb") as target:
        target.write(prologue)

        # Add files listed in file_list_fn
        with open(file_list_fn) as file_list:
            for source_fn in file_list:
                source_fn = source_fn.replace("/", os.path.sep).strip()
                if source_fn and source_fn[0] != "#":
                    addContents(os.path.join(source_base, source_fn), target)

        # Add all *.js files in module_dirs
        for module_base in module_dirs:
            for module_fn in os.listdir(module_base):
                if module_fn.endswith(".js"):
                    addContents(os.path.join(module_base, module_fn), target)


def addContents(source_fn, target):
    target.write("\n\n// " + source_fn + "\n\n")
    with open(source_fn) as source:
        for line in source:
            target.write(line)

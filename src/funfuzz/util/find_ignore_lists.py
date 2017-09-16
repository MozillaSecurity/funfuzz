#!/usr/bin/env python
# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Functions here attempt to find lists of bugs to ignore, e.g. via suppression files.
"""

from __future__ import absolute_import, print_function

import os

THIS_SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
THIS_REPO_PATH = os.path.abspath(os.path.join(THIS_SCRIPT_DIRECTORY, os.pardir))
REPO_PARENT_PATH = os.path.abspath(os.path.join(THIS_SCRIPT_DIRECTORY, os.pardir, os.pardir))

# Lets us combine ignore lists:
#   from private&public fuzzing repos
#   for project branches and for their base branches (e.g. mozilla-central)
#
# Given a target_repo "mozilla-central/ionmonkey" and a name "crashes.txt", returns a list of 2N absolute paths like:
#   ???/funfuzz*/known/mozilla-central/ionmonkey/crashes.txt
#   ???/funfuzz*/known/mozilla-central/crashes.txt


def find_ignore_lists(target_repo, needle):  # pylint: disable=missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    suppressions = []
    assert not target_repo.startswith("/")
    for name in sorted(os.listdir(REPO_PARENT_PATH)):
        if name.startswith("funfuzz"):
            known_path = os.path.join(REPO_PARENT_PATH, name, "known", target_repo)
            if os.path.isdir(known_path):
                while os.path.basename(known_path) != "known":
                    filename = os.path.join(known_path, needle)
                    if os.path.exists(filename):
                        suppressions.append(filename)
                    known_path = os.path.dirname(known_path)
    assert suppressions
    return suppressions

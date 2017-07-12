#!/usr/bin/env python
# coding=utf-8
# pylint: disable=invalid-name,missing-docstring
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import absolute_import, print_function

import os

THIS_SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
THIS_REPO_PATH = os.path.abspath(os.path.join(THIS_SCRIPT_DIRECTORY, os.pardir))
REPO_PARENT_PATH = os.path.abspath(os.path.join(THIS_SCRIPT_DIRECTORY, os.pardir, os.pardir))

# Lets us combine ignore lists:
#   from private&public fuzzing repos
#   for project branches and for their base branches (e.g. mozilla-central)
#
# Given a targetRepo "mozilla-central/ionmonkey" and a name "crashes.txt", returns a list of 2N absolute paths like:
#   ???/funfuzz*/known/mozilla-central/ionmonkey/crashes.txt
#   ???/funfuzz*/known/mozilla-central/crashes.txt


def findIgnoreLists(targetRepo, needle):
    r = []
    assert not targetRepo.startswith("/")
    for name in sorted(os.listdir(REPO_PARENT_PATH)):
        if name.startswith("funfuzz"):
            knownPath = os.path.join(REPO_PARENT_PATH, name, "known", targetRepo)
            if os.path.isdir(knownPath):
                while os.path.basename(knownPath) != "known":
                    filename = os.path.join(knownPath, needle)
                    if os.path.exists(filename):
                        r.append(filename)
                    knownPath = os.path.dirname(knownPath)
    assert r
    return r

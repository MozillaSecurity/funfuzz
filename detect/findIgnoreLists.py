#!/usr/bin/env python

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
    assert len(r) > 0
    return r

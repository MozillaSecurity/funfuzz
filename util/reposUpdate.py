#!/usr/bin/env python
# coding=utf-8
# pylint: disable=invalid-name,missing-docstring
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# To update specified repositories to default tip and provide a short list of latest checkins.
# Only supports hg (Mercurial) for now.
#
# Assumes that the repositories are located in ../../trees/*.

from __future__ import absolute_import, print_function

from copy import deepcopy
import logging
import os
import time

from . import subprocesses as sps


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

THIS_SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
REPO_PARENT_PATH = os.path.abspath(os.path.join(THIS_SCRIPT_DIRECTORY, os.pardir, os.pardir))

# Add your repository here. Note that Valgrind does not have a hg repository.
REPOS = ['gecko-dev', 'octo'] + \
    ['mozilla-' + x for x in ['inbound', 'central', 'beta', 'release']]

if sps.isWin:
    git_64bit_path = os.path.normpath(os.path.join(os.getenv('PROGRAMFILES'), 'Git', 'bin', 'git.exe'))
    git_32bit_path = os.path.normpath(os.path.join(os.getenv('PROGRAMFILES(X86)'), 'Git', 'bin', 'git.exe'))
    if os.path.isfile(git_64bit_path):
        GITBINARY = git_64bit_path
    elif os.path.isfile(git_32bit_path):
        GITBINARY = git_32bit_path
    else:
        raise OSError("Git binary not found")
else:
    GITBINARY = 'git'


def typeOfRepo(r):
    """Return the type of repository."""
    repoList = []
    repoList.append('.hg')
    repoList.append('.git')
    for rtype in repoList:
        if os.path.isdir(os.path.join(r, rtype)):
            return rtype[1:]
    raise Exception('Type of repository located at ' + r + ' cannot be determined.')


def updateRepo(repo):
    """Update a repository. Return False if missing; return True if successful; raise an exception if updating fails."""
    assert os.path.isdir(repo)
    repoType = typeOfRepo(repo)

    if repoType == 'hg':
        sps.timeSubprocess(['hg', 'pull', '-u'],
                           ignoreStderr=True, combineStderr=True, cwd=repo, vb=True)
        sps.timeSubprocess(['hg', 'log', '-r', 'default'], cwd=repo, vb=True)
    elif repoType == 'git':
        # Ignore exit codes so the loop can continue retrying up to number of counts.
        gitenv = deepcopy(os.environ)
        if sps.isWin:
            gitenv['GIT_SSH_COMMAND'] = "~/../../mozilla-build/msys/bin/ssh.exe -F ~/.ssh/config"
        sps.timeSubprocess([GITBINARY, 'pull', '--rebase'], env=gitenv,
                           ignoreStderr=True, combineStderr=True, ignoreExitCode=True, cwd=repo, vb=True)
    else:
        raise Exception('Unknown repository type: ' + repoType)

    return True


def updateRepos():
    """Update Mercurial and Git repositories located in ~ and ~/trees ."""
    trees = [
        os.path.normpath(os.path.join(REPO_PARENT_PATH)),
        os.path.normpath(os.path.join(REPO_PARENT_PATH, 'trees'))
    ]
    for tree in trees:
        for name in sorted(os.listdir(tree)):
            namePath = os.path.join(tree, name)
            if os.path.isdir(namePath) and (name in REPOS or name.startswith("funfuzz")):
                print("Updating %s ..." % name)
                updateRepo(namePath)


def main():
    logger.info(time.asctime())
    try:
        updateRepos()
    except OSError as e:
        print("WARNING: OSError hit:")
        print(e)
    logger.info(time.asctime())


if __name__ == '__main__':
    main()

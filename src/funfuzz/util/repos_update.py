# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""To update specified repositories to default tip and provide a short list of latest checkins.
Only supports hg (Mercurial) for now.

Assumes that the repositories are located in ../../trees/*.
"""

from __future__ import absolute_import

from copy import deepcopy
import logging
import os
import platform
import time

import pip
from . import subprocesses as sps


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

# Add your repository here. Note that Valgrind does not have a hg repository.
REPOS = ['gecko-dev', 'octo'] + \
    ['mozilla-' + x for x in ['inbound', 'central', 'beta', 'release']]

if sps.isWin:
    # pylint: disable=invalid-name
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


def typeOfRepo(r):  # pylint: disable=invalid-name,missing-param-doc,missing-raises-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Return the type of repository."""
    repo_types = []
    repo_types.append('.hg')
    repo_types.append('.git')
    for rtype in repo_types:
        if os.path.isdir(os.path.join(r, rtype)):
            return rtype[1:]
    raise Exception('Type of repository located at ' + r + ' cannot be determined.')


def update_funfuzz():
    """Updates the funfuzz repository."""
    # funfuzz repository assumed to be located at ~/funfuzz
    funfuzz_dir = sps.normExpUserPath(os.path.join("~", "funfuzz"))
    assert os.path.isdir(funfuzz_dir)
    assert typeOfRepo(funfuzz_dir) == "git"
    if pip.main(["install", "--upgrade", funfuzz_dir]) and platform.system() == "Linux":
        logger.info('\npip errored out, retrying with "--user"\n')
        pip.main(["install", "--user", "--upgrade", funfuzz_dir])


def updateRepo(repo):  # pylint: disable=invalid-name,missing-param-doc,missing-raises-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Update a repository. Return False if missing; return True if successful; raise an exception if updating fails."""
    assert os.path.isdir(repo)
    repo_type = typeOfRepo(repo)

    if repo_type == 'hg':
        sps.timeSubprocess(['hg', 'pull', '-u'],
                           ignoreStderr=True, combineStderr=True, cwd=repo, vb=True)
        sps.timeSubprocess(['hg', 'log', '-r', 'default'], cwd=repo, vb=True)
    elif repo_type == 'git':
        # Ignore exit codes so the loop can continue retrying up to number of counts.
        gitenv = deepcopy(os.environ)
        if sps.isWin:
            gitenv['GIT_SSH_COMMAND'] = "~/../../mozilla-build/msys/bin/ssh.exe -F ~/.ssh/config"
        sps.timeSubprocess([GITBINARY, 'pull'], env=gitenv,
                           ignoreStderr=True, combineStderr=True, ignoreExitCode=True, cwd=repo, vb=True)
    else:
        raise Exception('Unknown repository type: ' + repo_type)

    return True


def updateRepos():  # pylint: disable=invalid-name
    """Update Mercurial and Git repositories located in ~ and ~/trees ."""
    home_dir = sps.normExpUserPath("~")
    trees = [
        os.path.normpath(os.path.join(home_dir)),
        os.path.normpath(os.path.join(home_dir, 'trees'))
    ]
    for tree in trees:
        for name in sorted(os.listdir(tree)):
            name_path = os.path.join(tree, name)
            if os.path.isdir(name_path) and (name in REPOS or (name.startswith("funfuzz") and "-" in name)):
                logger.info("Updating %s ...", name)
                updateRepo(name_path)


def main():  # pylint: disable=missing-docstring
    logger.info(time.asctime())
    try:
        update_funfuzz()
        updateRepos()
    except OSError as ex:
        logger.info("WARNING: OSError hit:")
        logger.info(ex)
    logger.info(time.asctime())


if __name__ == '__main__':
    main()

#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# To update specified repositories to default tip and provide a short list of latest checkins.
# Only supports hg (Mercurial) for now.
#
# Assumes that the repositories are located in ../../trees/*.

import logging
import os
import subprocesses as sps
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ESR_NOW = 31
ESR_NEXT = ESR_NOW + 7

path0 = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
path1 = os.path.abspath(os.path.join(path0, os.pardir))

# Add your repository here. Note that Valgrind does not have a hg repository.
REPOS = ['fuzzing'] + ['mozilla-' + x for x in [
            'inbound', 'central', 'aurora', 'beta', 'release',
            'esr' + str(ESR_NOW), 'esr' + str(ESR_NEXT)
    ]
]

def typeOfRepo(r):
    '''Returns the type of repository.'''
    repoList = []
    repoList.append('.hg')
    #repoList.append('.git')
    for rtype in repoList:
        try:
            os.mkdir(os.path.join(r, rtype))
            os.rmdir(os.path.join(r, rtype))
        except OSError as e:
            if 'File exists' in e or 'Cannot create a file when that file already exists' in e:
                return rtype[1:]
    raise Exception('Type of repository located at ' + r + ' cannot be determined.')


def updateRepo(repo):
    '''Updates repositories.'''
    repoLocation = os.path.join(path1, repo)

    if not os.path.exists(repoLocation):
        logger.debug(repo, "repository does not exist at %s\n" %  repoLocation)
        repoLocation = os.path.join(path1, 'trees', repo)

        if not os.path.exists(repoLocation):
            logger.debug(repo, "repository does not exist at %s\n" %  repoLocation)
            return False

    logger.info('Now in %s repository.' % repo)
    repoType = typeOfRepo(repoLocation)

    count = 0
    while count < 3:  # Try pulling 3 times per repository.
        if repoType == 'hg':
            hgPullRebaseStdout, retval = sps.timeSubprocess(
                # Ignore exit codes so the loop can continue retrying up to number of counts.
                ['hg', 'pull', '--rebase'], ignoreStderr=True, combineStderr=True,
                ignoreExitCode=True, cwd=repoLocation, vb=True)
        #elif repoType == 'git':
            # This needs to be looked at. When ready, re-enable in typeOfRepo function.
            # Ignore exit codes so the loop can continue retrying up to number of counts.
            # gitStdout, retval = sps.timeSubprocess(
            #     ['git', 'fetch'], ignoreStderr=True, combineStderr=True, ignoreExitCode=True,
            #     cwd=repoLocation, vb=True)
            # gitStdout, retval = sps.timeSubprocess(
            #     ['git', 'checkout'], ignoreStderr=True, combineStderr=True, ignoreExitCode=True,
            #     cwd=repoLocation, vb=True)
        else:
            raise Exception('Unknown repository type: ' + repoType)

        if ((retval == 255) or (retval == -1)) and \
            'hg pull: option --rebase not recognized' in hgPullRebaseStdout:
            # Exit if the "rebase =" line is absent from the [Extensions] section of ~/.hgrc
            logger.error('Please enable the rebase extension in .hgrc. Exiting.')
            sys.exit(1)
        # 255 is the return code for abnormal hg exit on POSIX.
        # -1 is the return code for abnormal hg exit on Windows.
        # Not sure about SVN.
        if (retval != 255) and (retval != -1):
            break

        count += 1
        if count == 3:
            logger.error('Script tried to pull thrice and failed every time. Exiting.')
            sys.exit(1)

    if repoType == 'hg' and repo != 'valgrind':
        logger.info('Updating %s repository.' % repo)
        sps.timeSubprocess(['hg', 'update', 'default'], cwd=repoLocation, combineStderr=True,
            ignoreStderr=True, vb=True)
        sps.timeSubprocess(['hg', 'log', '-l', '5'], cwd=repoLocation, vb=True)
    return True


def main():
    logger.info(sps.dateStr())

    for repo in REPOS:
        updateRepo(repo)

    logger.info(sps.dateStr())


if __name__ == '__main__':
    main()

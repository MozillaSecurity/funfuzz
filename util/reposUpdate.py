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
        if os.path.isdir(os.path.join(r, rtype)):
            return rtype[1:]
    raise Exception('Type of repository located at ' + r + ' cannot be determined.')


def updateRepo(repo):
    '''Updates a repository. Returns False if missing; returns True if successful; raises an exception if updating fails.'''

    # Find the repo, or return False if we can't find it
    locs = [
        os.path.normpath(os.path.join(path1, repo)),
        os.path.normpath(os.path.join(path1, 'trees', repo))
    ]
    for loc in locs:
        if os.path.isdir(loc):
            repoLocation = loc
            break
    else:
        logger.info("We didn't find a repo in any of: %s\n" % repr(locs))
        return False

    logger.info('Found %s repository in %s' % (repo, repoLocation))
    repoType = typeOfRepo(repoLocation)

    # Update the repo, or sys.exit(1) if we can't update it
    if repoType == 'hg':
        _, retval = sps.timeSubprocess(['hg', 'pull', '-u'],
            ignoreStderr=True, combineStderr=True, cwd=repoLocation, vb=True)
        sps.timeSubprocess(['hg', 'log', '-r', 'default'],
            cwd=repoLocation, vb=True)
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

    return True


def main():
    logger.info(sps.dateStr())

    for repo in REPOS:
        updateRepo(repo)

    logger.info(sps.dateStr())


if __name__ == '__main__':
    main()

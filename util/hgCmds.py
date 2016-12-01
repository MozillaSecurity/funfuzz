#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import ConfigParser
import os
import re
import sys
import subprocess

import subprocesses as sps


def destroyPyc(repoDir):
    # This is roughly equivalent to ['hg', 'purge', '--all', '--include=**.pyc'])
    # but doesn't run into purge's issues (incompatbility with -R, requiring an hg extension)
    for root, dirs, files in os.walk(repoDir):
        for fn in files:
            if fn.endswith(".pyc"):
                os.remove(os.path.join(root, fn))
        if '.hg' in dirs:
            # Don't visit .hg dir
            dirs.remove('.hg')


def ensureMqEnabled():
    """Ensure that mq is enabled in the ~/.hgrc file."""
    usrHgrc = os.path.join(os.path.expanduser('~'), '.hgrc')
    assert os.path.isfile(usrHgrc)

    usrHgrcCfg = ConfigParser.SafeConfigParser()
    usrHgrcCfg.read(usrHgrc)

    try:
        usrHgrcCfg.get('extensions', 'mq')
    except ConfigParser.NoOptionError:
        raise Exception('Please first enable mq in ~/.hgrc by having "mq =" in [extensions].')


def findCommonAncestor(repoDir, a, b):
    return sps.captureStdout(['hg', '-R', repoDir, 'log', '-r', 'ancestor(' + a + ',' + b + ')',
                              '--template={node|short}'])[0]


def isAncestor(repoDir, a, b):
    """Return true iff |a| is an ancestor of |b|. Throw if |a| or |b| does not exist."""
    return sps.captureStdout(['hg', '-R', repoDir, 'log', '-r', a + ' and ancestor(' + a + ',' + b + ')',
                              '--template={node|short}'])[0] != ""


def existsAndIsAncestor(repoDir, a, b):
    """Return true iff |a| exists and is an ancestor of |b|."""
    # Takes advantage of "id(badhash)" being the empty set, in contrast to just "badhash", which is an error
    out = sps.captureStdout(['hg', '-R', repoDir, 'log', '-r', a + ' and ancestor(' + a + ',' + b + ')',
                             '--template={node|short}'], combineStderr=True, ignoreExitCode=True)[0]
    return out != "" and out.find("abort: unknown revision") < 0


def getCsetHashFromBisectMsg(msg):
    # Example bisect msg: "Testing changeset 41831:4f4c01fb42c3 (2 changesets remaining, ~1 tests)"
    r = re.compile(r"(^|.* )(\d+):(\w{12}).*")
    m = r.match(msg)
    if m:
        return m.group(3)

assert getCsetHashFromBisectMsg("x 12345:abababababab") == "abababababab"
assert getCsetHashFromBisectMsg("x 12345:123412341234") == "123412341234"
assert getCsetHashFromBisectMsg("12345:abababababab y") == "abababababab"


def getRepoHashAndId(repoDir, repoRev='parents() and default'):
    """Return the repository hash and id, and whether it is on default.

    It will also ask what the user would like to do, should the repository not be on default.
    """
    # This returns null if the repository is not on default.
    hgLogTmplList = ['hg', '-R', repoDir, 'log', '-r', repoRev,
                     '--template', '{node|short} {rev}']
    hgIdFull = sps.captureStdout(hgLogTmplList)[0]
    onDefault = bool(hgIdFull)
    if not onDefault:
        updateDefault = raw_input('Not on default tip! ' +
                                  'Would you like to (a)bort, update to (d)efault, or (u)se this rev: ')
        updateDefault = updateDefault.strip()
        if updateDefault == 'a':
            print 'Aborting...'
            sys.exit(0)
        elif updateDefault == 'd':
            subprocess.check_call(['hg', '-R', repoDir, 'update', 'default'])
            onDefault = True
        elif updateDefault == 'u':
            hgLogTmplList = ['hg', '-R', repoDir, 'log', '-r', 'parents()', '--template',
                             '{node|short} {rev}']
        else:
            raise Exception('Invalid choice.')
        hgIdFull = sps.captureStdout(hgLogTmplList)[0]
    assert hgIdFull != ''
    (hgIdChangesetHash, hgIdLocalNum) = hgIdFull.split(' ')
    sps.vdump('Finished getting the hash and local id number of the repository.')
    return hgIdChangesetHash, hgIdLocalNum, onDefault


def getRepoNameFromHgrc(repoDir):
    """Look in the hgrc file in the .hg directory of the repository and return the name."""
    assert isRepoValid(repoDir)
    hgCfg = ConfigParser.SafeConfigParser()
    hgCfg.read(sps.normExpUserPath(os.path.join(repoDir, '.hg', 'hgrc')))
    # Not all default entries in [paths] end with "/".
    return [i for i in hgCfg.get('paths', 'default').split('/') if i][-1]


def isRepoValid(repo):
    """Check that a repository is valid by ensuring that the hgrc file is around."""
    return os.path.isfile(sps.normExpUserPath(os.path.join(repo, '.hg', 'hgrc')))


def patchHgRepoUsingMq(patchFile, workingDir=os.getcwdu()):
    # We may have passed in the patch with or without the full directory.
    patchAbsPath = os.path.abspath(sps.normExpUserPath(patchFile))
    pname = os.path.basename(patchAbsPath)
    assert pname != ''
    qimportOutput, qimportRetCode = sps.captureStdout(['hg', '-R', workingDir, 'qimport', patchAbsPath],
                                                      combineStderr=True, ignoreStderr=True,
                                                      ignoreExitCode=True)
    if qimportRetCode != 0:
        if 'already exists' in qimportOutput:
            print "A patch with the same name has already been qpush'ed. Please qremove it first."
        raise Exception('Return code from `hg qimport` is: ' + str(qimportRetCode))

    print("Patch qimport'ed..."),

    qpushOutput, qpushRetCode = sps.captureStdout(['hg', '-R', workingDir, 'qpush', pname],
                                                  combineStderr=True, ignoreStderr=True)
    assert ' is empty' not in qpushOutput, "Patch to be qpush'ed should not be empty."

    if qpushRetCode != 0:
        hgQpopQrmAppliedPatch(patchFile, workingDir)
        print 'You may have untracked .rej or .orig files in the repository.'
        print '`hg status` output of the repository of interesting files in ' + workingDir + ' :'
        subprocess.check_call(['hg', '-R', workingDir, 'status', '--modified', '--added',
                               '--removed', '--deleted'])
        raise Exception('Return code from `hg qpush` is: ' + str(qpushRetCode))

    print("Patch qpush'ed. Continuing..."),
    return pname


def hgQpopQrmAppliedPatch(patchFile, repoDir):
    """Remove applied patch using `hg qpop` and `hg qdelete`."""
    qpopOutput, qpopRetCode = sps.captureStdout(['hg', '-R', repoDir, 'qpop'],
                                                combineStderr=True, ignoreStderr=True,
                                                ignoreExitCode=True)
    if qpopRetCode != 0:
        print '`hg qpop` output is: ' + qpopOutput
        raise Exception('Return code from `hg qpop` is: ' + str(qpopRetCode))

    print "Patch qpop'ed...",
    subprocess.check_call(['hg', '-R', repoDir, 'qdelete', os.path.basename(patchFile)])
    print "Patch qdelete'd."

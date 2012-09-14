#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import re
import sys
import subprocess
from ConfigParser import SafeConfigParser

from subprocesses import captureStdout, isVM, normExpUserPath, vdump

def findCommonAncestor(repoDir, a, b):
    return captureStdout(['hg', '-R', repoDir, 'log', '-r', 'ancestor(' + a + ',' + b + ')',
                          '--template={node|short}'])[0]

def getCsetHashFromBisectMsg(str):
    # Example bisect msg: "Testing changeset 41831:4f4c01fb42c3 (2 changesets remaining, ~1 tests)"
    r = re.compile(r"(^|.* )(\d+):(\w{12}).*")
    m = r.match(str)
    if m:
        return m.group(3)

assert getCsetHashFromBisectMsg("x 12345:abababababab") == "abababababab"
assert getCsetHashFromBisectMsg("x 12345:123412341234") == "123412341234"
assert getCsetHashFromBisectMsg("12345:abababababab y") == "abababababab"

def getMcRepoDir():
    '''Returns default m-c repository location and its base directory depending on machine.'''
    if isVM() == ('Windows', True):  # Self-selected presets in custom VMs
        baseDir = os.path.join('z:', os.sep)
    elif isVM() == ('Linux', True):  # Self-selected presets in custom VMs
        baseDir = os.path.join('/', 'mnt', 'hgfs')
    else:
        baseDir = '~'
    mcRepoDir = normExpUserPath(os.path.join(baseDir, 'trees', 'mozilla-central'))
    assert getRepoNameFromHgrc(os.path.join(mcRepoDir, '.hg', 'hgrc')) == 'mozilla-central'
    return baseDir, mcRepoDir

def getRepoHashAndId(repoDir, repoRev='parents() and default'):
    '''
    This function returns the repository hash and id, and whether it is on default.
    It also asks what the user would like to do, should the repository not be on default.
    '''
    # This returns null if the repository is not on default.
    hgLogTmplList = ['hg', '-R', repoDir, 'log', '-r', repoRev,
                     '--template', '{node|short} {rev}']
    hgIdFull = captureStdout(hgLogTmplList)[0]
    onDefault = bool(hgIdFull)
    if not onDefault:
        updateDefault = raw_input('Not on default tip! ' + \
            'Would you like to (a)bort, update to (d)efault, or (u)se this rev: ')
        if updateDefault == 'a':
            print 'Aborting...'
            sys.exit(0)
        elif updateDefault == 'd':
            subprocess.check_call(['hg', '-R', repoDir, 'up', 'default'])
            onDefault = True
        elif updateDefault == 'u':
            hgLogTmplList = ['hg', '-R', repoDir, 'log', '-r', 'parents()', '--template',
                             '{node|short} {rev}']
        else:
            raise Exception('Invalid choice.')
        hgIdFull = captureStdout(hgLogTmplList)[0]
    assert hgIdFull != ''
    (hgIdChangesetHash, hgIdLocalNum) = hgIdFull.split(' ')
    vdump('Finished getting the hash and local id number of the repository.')
    return hgIdChangesetHash, hgIdLocalNum, onDefault

def getRepoNameFromHgrc(hgrcpath):
    '''Looks in the hgrc file in the .hg directory of the repository and returns the name.'''
    assert os.path.isfile(hgrcpath)
    hgCfg = SafeConfigParser()
    hgCfg.read(hgrcpath)
    # Not all default entries in [paths] end with "/".
    return [i for i in hgCfg.get('paths', 'default').split('/') if i][-1]

def isAncestor(a, b):
    return findCommonAncestor(a, b) == a

def patchHgRepoUsingMq(patchLoc, workingDir=os.getcwdu()):
    # We may have passed in the patch with or without the full directory.
    p = os.path.abspath(normExpUserPath(patchLoc))
    pname = os.path.basename(p)
    assert (p, pname) != ('','')
    subprocess.check_call(['hg', '-R', workingDir, 'qimport', p])
    vdump("Patch qimport'ed.")
    try:
        subprocess.check_call(['hg', '-R', workingDir, 'qpush', pname])
        vdump("Patch qpush'ed.")
    except subprocess.CalledProcessError:
        subprocess.check_call(['hg', '-R', workingDir, 'qpop'])
        subprocess.check_call(['hg', '-R', workingDir, 'qdelete', pname])
        print 'You may have untracked .rej files in the repository.'
        print '`hg st` output of the repository in ' + workingDir + ' :'
        subprocess.check_call(['hg', '-R', workingDir, 'st'])
        hgPurgeAns = str(raw_input('Do you want to run `hg purge`? (y/n): '))
        assert hgPurgeAns.lower() in ('y', 'n')
        if hgPurgeAns == 'y':
            subprocess.check_call(['hg', '-R', workingDir, 'purge'])
        raise Exception(format_exc())
    return pname

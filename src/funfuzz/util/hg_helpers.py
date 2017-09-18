#!/usr/bin/env python
# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Helper functions involving Mercurial (hg).
"""

from __future__ import absolute_import, print_function

import ConfigParser  # pylint: disable=bad-python3-import,import-error
import os
import re
import sys
import subprocess

from . import subprocesses as sps


try:
    input = raw_input  # pylint: disable=invalid-name,raw_input-builtin,redefined-builtin
except NameError:
    pass


def destroyPyc(repoDir):  # pylint: disable=invalid-name,missing-docstring
    # This is roughly equivalent to ['hg', 'purge', '--all', '--include=**.pyc'])
    # but doesn't run into purge's issues (incompatbility with -R, requiring an hg extension)
    for root, dirs, files in os.walk(repoDir):
        for fn in files:  # pylint: disable=invalid-name
            if fn.endswith(".pyc"):
                os.remove(os.path.join(root, fn))
        if '.hg' in dirs:
            # Don't visit .hg dir
            dirs.remove('.hg')


def ensureMqEnabled():  # pylint: disable=invalid-name,missing-raises-doc
    """Ensure that mq is enabled in the ~/.hgrc file."""
    user_hgrc = os.path.join(os.path.expanduser('~'), '.hgrc')
    assert os.path.isfile(user_hgrc)

    user_hgrc_cfg = ConfigParser.SafeConfigParser()
    user_hgrc_cfg.read(user_hgrc)

    try:
        user_hgrc_cfg.get('extensions', 'mq')
    except ConfigParser.NoOptionError:
        raise Exception('Please first enable mq in ~/.hgrc by having "mq =" in [extensions].')


def findCommonAncestor(repoDir, a, b):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    return sps.captureStdout(['hg', '-R', repoDir, 'log', '-r', 'ancestor(' + a + ',' + b + ')',
                              '--template={node|short}'])[0]


def isAncestor(repoDir, a, b):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Return true iff |a| is an ancestor of |b|. Throw if |a| or |b| does not exist."""
    return sps.captureStdout(['hg', '-R', repoDir, 'log', '-r', a + ' and ancestor(' + a + ',' + b + ')',
                              '--template={node|short}'])[0] != ""


def existsAndIsAncestor(repoDir, a, b):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Return true iff |a| exists and is an ancestor of |b|."""
    # Takes advantage of "id(badhash)" being the empty set, in contrast to just "badhash", which is an error
    out = sps.captureStdout(['hg', '-R', repoDir, 'log', '-r', a + ' and ancestor(' + a + ',' + b + ')',
                             '--template={node|short}'], combineStderr=True, ignoreExitCode=True)[0]
    return out != "" and out.find("abort: unknown revision") < 0


def getCsetHashFromBisectMsg(msg):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    # Example bisect msg: "Testing changeset 41831:4f4c01fb42c3 (2 changesets remaining, ~1 tests)"
    rgx = re.compile(r"(^|.* )(\d+):(\w{12}).*")
    matched = rgx.match(msg)
    if matched:
        return matched.group(3)


assert getCsetHashFromBisectMsg("x 12345:abababababab") == "abababababab"
assert getCsetHashFromBisectMsg("x 12345:123412341234") == "123412341234"
assert getCsetHashFromBisectMsg("12345:abababababab y") == "abababababab"


def getRepoHashAndId(repoDir, repoRev='parents() and default'):  # pylint: disable=invalid-name,missing-param-doc
    # pylint: disable=missing-raises-doc,missing-return-doc,missing-return-type-doc,missing-type-doc
    """Return the repository hash and id, and whether it is on default.

    It will also ask what the user would like to do, should the repository not be on default.
    """
    # This returns null if the repository is not on default.
    hg_log_template_cmds = ['hg', '-R', repoDir, 'log', '-r', repoRev,
                            '--template', '{node|short} {rev}']
    hg_id_full = sps.captureStdout(hg_log_template_cmds)[0]
    is_on_default = bool(hg_id_full)
    if not is_on_default:
        update_default = input("Not on default tip! "
                               "Would you like to (a)bort, update to (d)efault, or (u)se this rev: ")
        update_default = update_default.strip()
        if update_default == 'a':
            print("Aborting...")
            sys.exit(0)
        elif update_default == 'd':
            subprocess.check_call(['hg', '-R', repoDir, 'update', 'default'])
            is_on_default = True
        elif update_default == 'u':
            hg_log_template_cmds = ['hg', '-R', repoDir, 'log', '-r', 'parents()', '--template',
                                    '{node|short} {rev}']
        else:
            raise Exception('Invalid choice.')
        hg_id_full = sps.captureStdout(hg_log_template_cmds)[0]
    assert hg_id_full != ''
    (hg_id_hash, hg_id_local_num) = hg_id_full.split(' ')
    sps.vdump('Finished getting the hash and local id number of the repository.')
    return hg_id_hash, hg_id_local_num, is_on_default


def getRepoNameFromHgrc(repoDir):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Look in the hgrc file in the .hg directory of the repository and return the name."""
    assert isRepoValid(repoDir)
    hgrc_cfg = ConfigParser.SafeConfigParser()
    hgrc_cfg.read(sps.normExpUserPath(os.path.join(repoDir, '.hg', 'hgrc')))
    # Not all default entries in [paths] end with "/".
    return [i for i in hgrc_cfg.get('paths', 'default').split('/') if i][-1]


def isRepoValid(repo):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Check that a repository is valid by ensuring that the hgrc file is around."""
    return os.path.isfile(sps.normExpUserPath(os.path.join(repo, '.hg', 'hgrc')))


def patchHgRepoUsingMq(patchFile, workingDir=None):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    workingDir = workingDir or (
        os.getcwdu() if sys.version_info.major == 2 else os.getcwd())  # pylint: disable=no-member
    # We may have passed in the patch with or without the full directory.
    patch_abs_path = os.path.abspath(sps.normExpUserPath(patchFile))
    pname = os.path.basename(patch_abs_path)
    assert pname != ''
    qimport_output, qimport_return_code = sps.captureStdout(['hg', '-R', workingDir, 'qimport', patch_abs_path],
                                                            combineStderr=True, ignoreStderr=True,
                                                            ignoreExitCode=True)
    if qimport_return_code != 0:
        if 'already exists' in qimport_output:
            print("A patch with the same name has already been qpush'ed. Please qremove it first.")
        raise Exception('Return code from `hg qimport` is: ' + str(qimport_return_code))

    print("Patch qimport'ed...", end=" ")

    qpush_output, qpush_return_code = sps.captureStdout(['hg', '-R', workingDir, 'qpush', pname],
                                                        combineStderr=True, ignoreStderr=True)
    assert ' is empty' not in qpush_output, "Patch to be qpush'ed should not be empty."

    if qpush_return_code != 0:
        hgQpopQrmAppliedPatch(patchFile, workingDir)
        print("You may have untracked .rej or .orig files in the repository.")
        print("`hg status` output of the repository of interesting files in %s :" % workingDir)
        subprocess.check_call(['hg', '-R', workingDir, 'status', '--modified', '--added',
                               '--removed', '--deleted'])
        raise Exception('Return code from `hg qpush` is: ' + str(qpush_return_code))

    print("Patch qpush'ed. Continuing...", end=" ")
    return pname


def hgQpopQrmAppliedPatch(patchFile, repoDir):  # pylint: disable=invalid-name,missing-param-doc,missing-raises-doc
    # pylint: disable=missing-type-doc
    """Remove applied patch using `hg qpop` and `hg qdelete`."""
    qpop_output, qpop_return_code = sps.captureStdout(['hg', '-R', repoDir, 'qpop'],
                                                      combineStderr=True, ignoreStderr=True,
                                                      ignoreExitCode=True)
    if qpop_return_code != 0:
        print("`hg qpop` output is: " % qpop_output)
        raise Exception('Return code from `hg qpop` is: ' + str(qpop_return_code))

    print("Patch qpop'ed...", end=" ")
    subprocess.check_call(['hg', '-R', repoDir, 'qdelete', os.path.basename(patchFile)])
    print("Patch qdelete'd.")

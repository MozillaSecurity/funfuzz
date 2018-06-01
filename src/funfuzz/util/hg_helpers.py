# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Helper functions involving Mercurial (hg).
"""

from __future__ import absolute_import, print_function, unicode_literals  # isort:skip

from builtins import input  # pylint: disable=redefined-builtin
import configparser
import os
import re
import sys

from . import subprocesses as sps

if sys.version_info.major == 2:
    from pathlib2 import Path
    if os.name == "posix":
        import subprocess32 as subprocess  # pylint: disable=import-error
else:
    from pathlib import Path  # pylint: disable=import-error
    import subprocess


def destroyPyc(repo_dir):  # pylint: disable=invalid-name,missing-docstring
    # This is roughly equivalent to ["hg", "purge", "--all", "--include=**.pyc"])
    # but doesn't run into purge's issues (incompatbility with -R, requiring an hg extension)
    for root, dirs, files in os.walk(str(repo_dir)):
        for fn in files:  # pylint: disable=invalid-name
            if fn.endswith(".pyc"):
                (Path(root) / fn).unlink()
        if ".hg" in dirs:
            # Don't visit .hg dir
            dirs.remove(".hg")


def ensure_mq_enabled():
    """Ensure that mq is enabled in the ~/.hgrc file.

    Raises:
        NoOptionError: Raises if an mq entry is not found in [extensions]
    """
    user_hgrc = Path.home() / ".hgrc"
    assert user_hgrc.is_file()  # pylint: disable=no-member

    user_hgrc_cfg = configparser.SafeConfigParser()
    user_hgrc_cfg.read(str(user_hgrc))

    try:
        user_hgrc_cfg.get("extensions", "mq")
    except configparser.NoOptionError:
        print('Please first enable mq in ~/.hgrc by having "mq =" in [extensions].')
        raise


def findCommonAncestor(repo_dir, a, b):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    return subprocess.run(
        ["hg", "-R", str(repo_dir), "log", "-r", "ancestor(" + a + "," + b + ")", "--template={node|short}"],
        cwd=os.getcwdu() if sys.version_info.major == 2 else os.getcwd(),  # pylint: disable=no-member
        check=True,
        stdout=subprocess.PIPE,
        timeout=999
        ).stdout.decode("utf-8", errors="replace")


def isAncestor(repo_dir, a, b):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Return true iff |a| is an ancestor of |b|. Throw if |a| or |b| does not exist."""
    return subprocess.run(
        ["hg", "-R", str(repo_dir), "log", "-r", a + " and ancestor(" + a + "," + b + ")", "--template={node|short}"],
        cwd=os.getcwdu() if sys.version_info.major == 2 else os.getcwd(),  # pylint: disable=no-member
        check=True,
        stdout=subprocess.PIPE,
        timeout=999
        ).stdout.decode("utf-8", errors="replace") != ""


def existsAndIsAncestor(repo_dir, a, b):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Return true iff |a| exists and is an ancestor of |b|."""
    # Takes advantage of "id(badhash)" being the empty set, in contrast to just "badhash", which is an error
    out = subprocess.run(
        ["hg", "-R", str(repo_dir), "log", "-r", a + " and ancestor(" + a + "," + b + ")", "--template={node|short}"],
        cwd=os.getcwdu() if sys.version_info.major == 2 else os.getcwd(),  # pylint: disable=no-member
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        timeout=999
        ).stdout.decode("utf-8", errors="replace")
    return out != "" and out.find("abort: unknown revision") < 0


def get_cset_hash_from_bisect_msg(msg):
    """Extract the changeset hash from bisection output.

    Args:
        msg (str): Bisection output message.

    Returns:
        str: Changeset hash.

    Raises:
        ValueError: If required bisection output format does not allow changeset hash to be extracted properly.
    """
    rgx = re.compile(r"(^|.* )(\d+):(\w{12}).*")
    matched = rgx.match(msg)
    if matched:
        return matched.group(3)
    raise ValueError("Bisection output format required for hash extraction unavailable. The variable msg is: %s" % msg)


def get_repo_hash_and_id(repo_dir, repo_rev="parents() and default"):
    """Return the repository hash and id, and whether it is on default.

    It will also ask what the user would like to do, should the repository not be on default.

    Args:
        repo_dir (Path): Full path to the repository
        repo_rev (str): Intended Mercurial changeset details to retrieve

    Raises:
        ValueError: Raises if the input is invalid

    Returns:
        tuple: Changeset hash, local numerical ID, boolean on whether the repository is on default tip
    """
    # This returns null if the repository is not on default.
    hg_log_template_cmds = ["hg", "-R", str(repo_dir), "log", "-r", repo_rev,
                            "--template", "{node|short} {rev}"]
    hg_id_full = subprocess.run(
        hg_log_template_cmds,
        cwd=os.getcwdu() if sys.version_info.major == 2 else os.getcwd(),  # pylint: disable=no-member
        check=True,
        stdout=subprocess.PIPE,
        timeout=99
        ).stdout.decode("utf-8", errors="replace")
    is_on_default = bool(hg_id_full)
    if not is_on_default:
        update_default = input("Not on default tip! "
                               "Would you like to (a)bort, update to (d)efault, or (u)se this rev: ")
        update_default = update_default.strip()
        if update_default == "a":
            print("Aborting...")
            sys.exit(0)
        elif update_default == "d":
            subprocess.run(["hg", "-R", str(repo_dir), "update", "default"], check=True)
            is_on_default = True
        elif update_default == "u":
            hg_log_template_cmds = ["hg", "-R", str(repo_dir), "log", "-r", "parents()", "--template",
                                    "{node|short} {rev}"]
        else:
            raise ValueError("Invalid choice.")
        hg_id_full = subprocess.run(
            hg_log_template_cmds,
            cwd=os.getcwdu() if sys.version_info.major == 2 else os.getcwd(),  # pylint: disable=no-member
            check=True,
            stdout=subprocess.PIPE,
            timeout=99
            ).stdout.decode("utf-8", errors="replace")
    assert hg_id_full != ""
    (hg_id_hash, hg_id_local_num) = hg_id_full.split(" ")
    sps.vdump("Finished getting the hash and local id number of the repository.")
    return hg_id_hash, hg_id_local_num, is_on_default


def hgrc_repo_name(repo_dir):
    """Look in the hgrc file in the .hg directory of the Mercurial repository and return the name.

    Args:
        repo_dir (Path): Mercurial repository directory

    Returns:
        str: Returns the name of the Mercurial repository as indicated in the .hgrc
    """
    hgrc_cfg = configparser.SafeConfigParser()
    hgrc_cfg.read(str(repo_dir / ".hg" / "hgrc"))
    # Not all default entries in [paths] end with "/".
    return [i for i in hgrc_cfg.get("paths", "default").split("/") if i][-1]


def patch_hg_repo_with_mq(patch_file, repo_dir=None):
    """Use mq to patch the Mercurial repository

    Args:
        patch_file (Path): Full path to the patch
        repo_dir (Path): Working directory path

    Raises:
        OSError: Raises when `hg qimport` or `hg qpush` did not return a return code of 0

    Returns:
        str: Returns the name of the patch file
    """
    repo_dir = str(repo_dir) or (
        os.getcwdu() if sys.version_info.major == 2 else os.getcwd())  # pylint: disable=no-member
    # We may have passed in the patch with or without the full directory.
    patch_abs_path = patch_file.resolve()
    pname = patch_abs_path.name
    qimport_result = subprocess.run(
        ["hg", "-R", str(repo_dir), "qimport", patch_abs_path],
        cwd=os.getcwdu() if sys.version_info.major == 2 else os.getcwd(),  # pylint: disable=no-member
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        timeout=99)
    qimport_output, qimport_return_code = (qimport_result.stdout.decode("utf-8", errors="replace"),
                                           qimport_result.returncode)
    if qimport_return_code != 0:
        if "already exists" in qimport_output:
            print("A patch with the same name has already been qpush'ed. Please qremove it first.")
        raise OSError("Return code from `hg qimport` is: " + str(qimport_return_code))

    print("Patch qimport'ed...", end=" ")

    qpush_result = subprocess.run(
        ["hg", "-R", str(repo_dir), "qpush", pname],
        cwd=os.getcwdu() if sys.version_info.major == 2 else os.getcwd(),  # pylint: disable=no-member
        check=True,
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        timeout=99)
    qpush_output, qpush_return_code = qpush_result.stdout.decode("utf-8", errors="replace"), qpush_result.returncode
    assert " is empty" not in qpush_output, "Patch to be qpush'ed should not be empty."

    if qpush_return_code != 0:
        qpop_qrm_applied_patch(patch_file, repo_dir)
        print("You may have untracked .rej or .orig files in the repository.")
        print("`hg status` output of the repository of interesting files in %s :" % repo_dir)
        subprocess.run(["hg", "-R", str(repo_dir), "status", "--modified", "--added",
                        "--removed", "--deleted"], check=True)
        raise OSError("Return code from `hg qpush` is: " + str(qpush_return_code))

    print("Patch qpush'ed. Continuing...", end=" ")
    return pname


def qpop_qrm_applied_patch(patch_file, repo_dir):
    """Remove applied patch using `hg qpop` and `hg qdelete`.

    Args:
        patch_file (Path): Full path to the patch
        repo_dir (Path): Working directory path

    Raises:
        OSError: Raises when `hg qpop` did not return a return code of 0
    """
    qpop_result = subprocess.run(
        ["hg", "-R", str(repo_dir), "qpop"],
        cwd=os.getcwdu() if sys.version_info.major == 2 else os.getcwd(),  # pylint: disable=no-member
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        timeout=99)
    qpop_output, qpop_return_code = qpop_result.stdout.decode("utf-8", errors="replace"), qpop_result.returncode
    if qpop_return_code != 0:
        print("`hg qpop` output is: " + qpop_output)
        raise OSError("Return code from `hg qpop` is: " + str(qpop_return_code))

    print("Patch qpop'ed...", end=" ")
    subprocess.run(["hg", "-R", str(repo_dir), "qdelete", patch_file.name], check=True)
    print("Patch qdelete'd.")

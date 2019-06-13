# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""To update specified repositories to default tip and provide a short list of latest checkins.
Only supports hg (Mercurial) for now.

Assumes that the repositories are located in ../../trees/*.
"""

from copy import deepcopy
import logging
import os
from pathlib import Path
import platform
import subprocess
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

# Add your repository here.
REPOS = ["gecko-dev", "octo"] + ["mozilla-" + x for x in ["central"]]

if platform.system() == "Windows":
    # pylint: disable=invalid-name
    git_64bit_path = Path(os.getenv("PROGRAMFILES")) / "Git" / "bin" / "git.exe"
    git_32bit_path = Path(os.getenv("PROGRAMFILES(X86)")) / "Git" / "bin" / "git.exe"
    if git_64bit_path.is_file():
        GITBINARY = str(git_64bit_path)
    elif git_32bit_path.is_file():
        GITBINARY = str(git_32bit_path)
    else:
        raise OSError("Git binary not found")
else:
    GITBINARY = str("git")


def time_cmd(cmd, cwd=None, env=None, timeout=None):
    """Calculates and outputs the time a command takes.

    Args:
        cmd (list): Command to be run.
        cwd (str): Working directory command is to be executed in.
        env (dict): Working environment command is to be executed in.
        timeout (int): Timeout for the command.
    """
    if not env:
        env = deepcopy(os.environ)

    logger.info("\nRunning `%s` now..\n", " ".join(cmd))
    cmd_start = time.time()

    cmd = subprocess.run(cmd, cwd=cwd, env=env, timeout=timeout)

    cmd_end = time.time()
    logger.info("\n`%s` took %.3f seconds.\n", subprocess.list2cmdline(cmd.args), cmd_end - cmd_start)


def typeOfRepo(r):  # pylint: disable=invalid-name,missing-param-doc,missing-raises-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Return the type of repository."""
    repo_types = []
    repo_types.append(".hg")
    repo_types.append(".git")
    for rtype in repo_types:
        if (r / rtype).is_dir():
            return rtype[1:]
    raise OSError(f"Type of repository located at {r} cannot be determined.")


def updateRepo(repo):  # pylint: disable=invalid-name,missing-param-doc,missing-raises-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Update a repository. Return False if missing; return True if successful; raise an exception if updating fails."""
    repo.is_dir()
    repo_type = typeOfRepo(repo)

    if repo_type == "hg":
        hg_pull_cmd = ["hg", "--time", "pull", "-u"]
        logger.info("\nRunning `%s` now..\n", " ".join(hg_pull_cmd))
        out_hg_pull = subprocess.run(hg_pull_cmd, check=True, cwd=str(repo), stderr=subprocess.PIPE)
        logger.info('"%s" had the above output and took - %s',
                    subprocess.list2cmdline(out_hg_pull.args),
                    out_hg_pull.stderr.decode("utf-8", errors="replace").rstrip())

        hg_log_default_cmd = ["hg", "--time", "log", "-r", "default"]
        logger.info("\nRunning `%s` now..\n", " ".join(hg_log_default_cmd))
        out_hg_log_default = subprocess.run(hg_log_default_cmd, check=True, cwd=str(repo),
                                            stderr=subprocess.PIPE)
        logger.info('"%s" had the above output and took - %s',
                    subprocess.list2cmdline(out_hg_log_default.args),
                    out_hg_log_default.stderr.decode("utf-8", errors="replace").rstrip())
    elif repo_type == "git":
        # Ignore exit codes so the loop can continue retrying up to number of counts.
        gitenv = deepcopy(os.environ)
        if platform.system() == "Windows":
            gitenv["GIT_SSH_COMMAND"] = "~/../../mozilla-build/msys/bin/ssh.exe -F ~/.ssh/config"
        time_cmd([GITBINARY, "pull"], cwd=str(repo), env=gitenv)
    else:
        raise OSError(f"Unknown repository type: {repo_type}")

    return True


def updateRepos():  # pylint: disable=invalid-name
    """Update Mercurial and Git repositories located in ~ and ~/trees ."""
    home_dir = Path.home()
    trees = [
        home_dir,
        home_dir / "trees",
    ]
    for tree in trees:
        for name in sorted(os.listdir(str(tree))):
            name_path = Path(tree) / name
            if name_path.is_dir() and (name in REPOS or (name.startswith("funfuzz") and "-" in name)):
                logger.info("Updating %s ...", name)
                updateRepo(name_path)


def main():  # pylint: disable=missing-docstring
    logger.info(time.asctime())
    try:
        updateRepos()
    except OSError as ex:
        logger.info("WARNING: OSError hit:")
        logger.info(ex)
    logger.info(time.asctime())


if __name__ == "__main__":
    main()

# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Helper functions to compile SpiderMonkey shells.
"""

import io
import os
from pathlib import Path
import platform
from shlex import quote
import shutil
import subprocess


def ensure_cache_dir(base_dir):
    """Retrieve a cache directory for compiled shells to live in, and create one if needed.

    Args:
        base_dir (Path): Base directory to create the cache directory in

    Returns:
        Path: Returns the full shell-cache path
    """
    if not base_dir:
        base_dir = Path.home()
    cache_dir = base_dir / "shell-cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def autoconf_run(working_dir):
    """Run autoconf binaries corresponding to the platform.

    Args:
        working_dir (Path): Directory to be set as the current working directory
    """
    if platform.system() == "Darwin":
        # Total hack to support new and old Homebrew configs, we can probably just call autoconf213
        if shutil.which("brew"):
            autoconf213_mac_bin = "/usr/local/Cellar/autoconf213/2.13/bin/autoconf213"
        else:
            autoconf213_mac_bin = shutil.which("autoconf213")
        if not Path(autoconf213_mac_bin).is_file():
            autoconf213_mac_bin = "autoconf213"
        subprocess.run([autoconf213_mac_bin], check=True, cwd=str(working_dir))
    elif platform.system() == "Linux":
        if shutil.which("autoconf2.13"):
            subprocess.run(["autoconf2.13"], check=True, cwd=str(working_dir))
        elif shutil.which("autoconf-2.13"):
            subprocess.run(["autoconf-2.13"], check=True, cwd=str(working_dir))
        elif shutil.which("autoconf213"):
            subprocess.run(["autoconf213"], check=True, cwd=str(working_dir))
    elif platform.system() == "Windows":
        # Windows needs to call sh to be able to find autoconf.
        subprocess.run(["sh", "autoconf-2.13"], check=True, cwd=str(working_dir))


def envDump(shell, log):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc
    """Dump environment to a .fuzzmanagerconf file."""
    # Platform and OS detection for the spec, part of which is in:
    #   https://wiki.mozilla.org/Security/CrashSignatures
    fmconf_platform = "x86" if shell.build_opts.enable32 else "x86-64"

    fmconf_os = None
    if platform.system() == "Linux":
        fmconf_os = "linux"
    elif platform.system() == "Darwin":
        fmconf_os = "macosx"
    elif platform.system() == "Windows":
        fmconf_os = "windows"

    with io.open(str(log), "a", encoding="utf-8", errors="replace") as f:
        f.write("# Information about shell:\n# \n")

        f.write("# Create another shell in shell-cache like this one:\n")
        f.write(f"# python3 -u -m funfuzz.js.compile_shell "
                f'-b "{shell.build_opts.build_options_str}" -r {shell.get_hg_hash()}\n# \n')

        f.write("# Full environment is:\n")
        f.write(f"# {shell.get_env_full()}\n# \n")

        f.write("# Full configuration command with needed environment variables is:\n")
        f.write(f'# {" ".join(quote(str(x)) for x in shell.get_env_added())} '
                f'{" ".join(quote(str(x)) for x in shell.get_cfg_cmd_excl_env())}\n# \n')

        # .fuzzmanagerconf details
        f.write("\n")
        f.write("[Main]\n")
        f.write(f"platform = {fmconf_platform}\n")
        f.write(f"product = {shell.get_repo_name()}\n")
        f.write(f"product_version = {shell.get_hg_hash()}\n")
        f.write(f"os = {fmconf_os}\n")

        f.write("\n")
        f.write("[Metadata]\n")
        f.write(f"buildFlags = {shell.build_opts.build_options_str}\n")
        f.write(f'majorVersion = {shell.get_version().split(".")[0]}\n')
        f.write(f"pathPrefix = {shell.get_repo_dir()}/\n")
        f.write(f"version = {shell.get_version()}\n")


def extract_vers(objdir):  # pylint: disable=inconsistent-return-statements
    """Extract the version from js.pc and put it into *.fuzzmanagerconf.

    Args:
        objdir (Path): Full path to the objdir

    Raises:
        OSError: Raises when js.pc is not found

    Returns:
        str: Version number of the compiled js shell
    """
    jspc_file_path = objdir / "js" / "src" / "js.pc"
    # Moved to <objdir>/js/src/build/, see bug 1262241, Fx55 m-c rev 351194:2159959522f4
    jspc_new_file_path = objdir / "js" / "src" / "build" / "js.pc"

    if jspc_file_path.is_file():
        actual_path = jspc_file_path
    elif jspc_new_file_path.is_file():
        actual_path = jspc_new_file_path
    else:
        raise OSError("js.pc file not found - needed to extract the version number")

    with io.open(str(actual_path), mode="r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("Version: "):  # Sample line: "Version: 47.0a2"
                return line.split(": ")[1].rstrip()


def get_lock_dir_path(cache_dir_base, repo_dir, tbox_id=""):
    """Return the name of the lock directory.

    Args:
        cache_dir_base (Path): Base directory where the cache directory is located
        repo_dir (Path): Full path to the repository
        tbox_id (str): Tinderbox entry id

    Returns:
        Path: Full path to the shell cache lock directory
    """
    lockdir_name = f"shell-{repo_dir.name}-lock"
    if tbox_id:
        lockdir_name += f"-{tbox_id}"
    return ensure_cache_dir(cache_dir_base) / lockdir_name


def verify_full_win_pageheap(shell_path):
    """Turn on full page heap verification on Windows.

    Args:
        shell_path (Path): Path to the compiled js shell
    """
    # More info: https://msdn.microsoft.com/en-us/library/windows/hardware/ff543097(v=vs.85).aspx
    # or https://blogs.msdn.microsoft.com/webdav_101/2010/06/22/detecting-heap-corruption-using-gflags-and-dumps/
    gflags_bin_path = Path(os.getenv("PROGRAMW6432")) / "Debugging Tools for Windows (x64)" / "gflags.exe"
    if gflags_bin_path.is_file() and shell_path.is_file():
        print(subprocess.run([str(gflags_bin_path), "-p", "/enable", str(shell_path), "/full"],
                             check=True,
                             stderr=subprocess.STDOUT,
                             stdout=subprocess.PIPE).stdout)

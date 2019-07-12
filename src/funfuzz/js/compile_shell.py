# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Compiles SpiderMonkey shells on different platforms using various specified configuration parameters.
"""

import copy
import io
import multiprocessing
from optparse import OptionParser  # pylint: disable=deprecated-module
import os
from pathlib import Path
import platform
from shlex import quote
import shutil
import subprocess
import sys
import tarfile
import traceback

from pkg_resources import parse_version

from . import build_options
from . import inspect_shell
from ..util import file_system_helpers
from ..util import hg_helpers
from ..util import s3cache
from ..util import sm_compile_helpers
from ..util import subprocesses as sps
from ..util.lock_dir import LockDir

S3_SHELL_CACHE_DIRNAME = "shell-cache"  # Used by autobisectjs

if platform.system() == "Windows":
    MAKE_BINARY = "mozmake"
    CLANG_PARAMS = "-fallback"
    # CLANG_ASAN_PARAMS = "-fsanitize=address -Dxmalloc=myxmalloc"
    # Note that Windows ASan builds are still a work-in-progress
    CLANG_ASAN_PARAMS = ""
    CLANG_VER = "8.0.0"
    WIN_MOZBUILD_CLANG_PATH = Path.home() / ".mozbuild" / "clang"
else:
    MAKE_BINARY = "make"
    CLANG_PARAMS = ""
    CLANG_ASAN_PARAMS = "-fsanitize=address"
    SSE2_FLAGS = "-msse2 -mfpmath=sse"  # See bug 948321

if multiprocessing.cpu_count() > 2:
    COMPILATION_JOBS = multiprocessing.cpu_count() + 1
else:
    COMPILATION_JOBS = 3  # Other single/dual core computers


class CompiledShellError(Exception):
    """Error class unique to CompiledShell objects."""


class CompiledShell:  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """A CompiledShell object represents an actual compiled shell binary.

    Args:
        build_opts (object): Object containing the build options defined in build_options.py
        hg_hash (str): Changeset hash
    """
    def __init__(self, build_opts, hg_hash):
        self.shell_name_without_ext = build_options.computeShellName(build_opts, hg_hash)
        self.hg_hash = hg_hash
        self.build_opts = build_opts

        self.js_objdir = ""

        self.cfg = []
        self.destDir = ""  # pylint: disable=invalid-name
        self.added_env = ""
        self.full_env = ""
        self.js_cfg_file = ""

        self.js_version = ""

    @classmethod
    def main(cls, args=None):
        """Main function of CompiledShell class.

        Args:
            args (object): Additional parameters

        Returns:
            int: 0, to denote a successful compile and 1, to denote a failed compile
        """
        # logging.basicConfig(format="%(message)s", level=logging.INFO)
        try:
            return cls.run(args)
        except CompiledShellError as ex:
            print(repr(ex))
            # log.error(ex)
            return 1

    @staticmethod
    def run(argv=None):
        """Build a shell and place it in the autobisectjs cache.

        Args:
            argv (object): Additional parameters

        Returns:
            int: 0, to denote a successful compile
        """
        usage = "Usage: %prog [options]"
        parser = OptionParser(usage)
        parser.disable_interspersed_args()

        parser.set_defaults(
            build_opts="",
        )

        # Specify how the shell will be built.
        parser.add_option("-b", "--build",
                          dest="build_opts",
                          help='Specify build options, e.g. -b "--disable-debug --enable-optimize" '
                               "(python3 -m funfuzz.js.build_options --help)")

        parser.add_option("-r", "--rev",
                          dest="revision",
                          help="Specify revision to build")

        options = parser.parse_args(argv)[0]
        options.build_opts = build_options.parse_shell_opts(options.build_opts)

        with LockDir(sm_compile_helpers.get_lock_dir_path(Path.home(), options.build_opts.repo_dir)):
            if options.revision:
                shell = CompiledShell(options.build_opts, options.revision)
            else:
                local_orig_hg_hash = hg_helpers.get_repo_hash_and_id(options.build_opts.repo_dir)[0]
                shell = CompiledShell(options.build_opts, local_orig_hg_hash)

            obtainShell(shell, updateToRev=options.revision)
            print(shell.get_shell_cache_js_bin_path())

        return 0

    def get_cfg_cmd_excl_env(self):
        """Retrieve the configure command excluding the enviroment variables.

        Returns:
            list: Configure command
        """
        return self.cfg

    def set_cfg_cmd_excl_env(self, cfg):
        """Sets the configure command excluding the enviroment variables.

        Args:
            cfg (list): Configure command
        """
        self.cfg = cfg

    def set_env_added(self, added_env):
        """Set environment variables that were added.

        Args:
            added_env (list): Added environment variables
        """
        self.added_env = added_env

    def get_env_added(self):
        """Retrieve environment variables that were added.

        Returns:
            list: Added environment variables
        """
        return self.added_env

    def set_env_full(self, full_env):
        """Set the full environment including the newly added variables.

        Args:
            full_env (list): Full environment
        """
        self.full_env = full_env

    def get_env_full(self):
        """Retrieve the full environment including the newly added variables.

        Returns:
            list: Full environment
        """
        return self.full_env

    def get_hg_hash(self):
        """Retrieve the hash of the current changeset of the repository.

        Returns:
            str: Changeset hash
        """
        return self.hg_hash

    def get_js_cfg_path(self):
        """Retrieve the configure file in a js/src directory.

        Returns:
            Path: Full path to the configure file
        """
        self.js_cfg_file = self.get_repo_dir() / "js" / "src" / "configure"
        return self.js_cfg_file

    def get_js_objdir(self):
        """Retrieve the objdir of the js shell to be compiled.

        Returns:
            Path: Full path to the js shell objdir
        """
        return self.js_objdir

    def set_js_objdir(self, objdir):
        """Set the objdir of the js shell to be compiled.

        Args:
            objdir (Path): Full path to the objdir of the js shell to be compiled
        """
        self.js_objdir = objdir

    def get_repo_dir(self):
        """Retrieve the directory of a Mercurial repository.

        Returns:
            Path: Full path to the repository
        """
        return self.build_opts.repo_dir

    def get_repo_name(self):
        """Retrieve the name of a Mercurial repository.

        Returns:
            str: Name of the repository
        """
        return hg_helpers.hgrc_repo_name(self.build_opts.repo_dir)

    def get_s3_tar_name_with_ext(self):
        """Retrieve the name of the compressed shell tarball to be obtained from/sent to S3.

        Returns:
            str: Name of the tarball
        """
        return f"{self.get_shell_name_without_ext()}.tar.bz2"

    def get_s3_tar_with_ext_full_path(self):
        """Retrieve the path to the tarball downloaded from S3.

        Returns:
            Path: Full path to the tarball in the local shell cache directory
        """
        return sm_compile_helpers.ensure_cache_dir(Path.home()) / self.get_s3_tar_name_with_ext()

    def get_shell_cache_dir(self):
        """Retrieve the shell cache directory of the intended js binary.

        Returns:
            Path: Full path to the shell cache directory of the intended js binary
        """
        return sm_compile_helpers.ensure_cache_dir(Path.home()) / self.get_shell_name_without_ext()

    def get_shell_cache_js_bin_path(self):
        """Retrieve the full path to the js binary located in the shell cache.

        Returns:
            Path: Full path to the js binary in the shell cache
        """
        return (sm_compile_helpers.ensure_cache_dir(Path.home()) /
                self.get_shell_name_without_ext() / self.get_shell_name_with_ext())

    def get_shell_compiled_path(self):
        """Retrieve the full path to the original location of js binary compiled in the shell cache.

        Returns:
            Path: Full path to the original location of js binary compiled in the shell cache
        """
        full_path = self.get_js_objdir() / "dist" / "bin" / "js"
        return full_path.with_suffix(".exe") if platform.system() == "Windows" else full_path

    def get_shell_compiled_runlibs_path(self):
        """Retrieve the full path to the original location of the libraries of js binary compiled in the shell cache.

        Returns:
            Path: Full path to the original location of the libraries of js binary compiled in the shell cache
        """
        return [
            self.get_js_objdir() / "dist" / "bin" / runlib for runlib in inspect_shell.ALL_RUN_LIBS
        ]

    def get_shell_name_with_ext(self):
        """Retrieve the name of the compiled js shell with the file extension.

        Returns:
            str: Name of the compiled js shell with the file extension
        """
        # pylint complains if this line uses an f-string with nested if-else, see https://git.io/fxfSo
        return self.shell_name_without_ext + (".exe" if platform.system() == "Windows" else "")

    def get_shell_name_without_ext(self):
        """Retrieve the name of the compiled js shell without the file extension.

        Returns:
            str: Name of the compiled js shell without the file extension
        """
        return self.shell_name_without_ext

    def get_version(self):
        """Retrieve the version number of the js shell as extracted from js.pc

        Returns:
            str: Version number of the js shell
        """
        return self.js_version

    def set_version(self, js_version):
        """Set the version number of the js shell as extracted from js.pc

        Args:
            js_version (str): Version number of the js shell
        """
        self.js_version = js_version


def cfgJsCompile(shell):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc
    """Configures, compiles and copies a js shell according to required parameters."""
    print("Compiling...")  # Print *with* a trailing newline to avoid breaking other stuff
    js_objdir_path = shell.get_shell_cache_dir() / "objdir-js"
    js_objdir_path.mkdir()
    shell.set_js_objdir(js_objdir_path)

    sm_compile_helpers.autoconf_run(shell.get_repo_dir() / "js" / "src")
    cfgBin(shell)
    sm_compile(shell)
    inspect_shell.verifyBinary(shell)

    compile_log = shell.get_shell_cache_dir() / f"{shell.get_shell_name_without_ext()}.fuzzmanagerconf"
    if not compile_log.is_file():
        sm_compile_helpers.envDump(shell, compile_log)


def cfgBin(shell):  # pylint: disable=invalid-name,missing-param-doc,missing-raises-doc,missing-type-doc
    # pylint: disable=too-complex,too-many-branches,too-many-statements
    """Configure a binary according to required parameters."""
    cfg_cmds = []
    cfg_env = copy.deepcopy(os.environ)
    orig_cfg_env = copy.deepcopy(os.environ)
    if platform.system() != "Windows":
        cfg_env["AR"] = "ar"
    if shell.build_opts.enable32 and platform.system() == "Linux":
        # 32-bit shell on 32/64-bit x86 Linux
        cfg_env["PKG_CONFIG_LIBDIR"] = "/usr/lib/pkgconfig"
        # apt-get `libc6-dev-i386 g++-multilib` first, if on 64-bit Linux. (no matter Clang or GCC)
        cfg_env["CC"] = f"clang -m32 {SSE2_FLAGS}"
        cfg_env["CXX"] = f"clang++ -m32 {SSE2_FLAGS}"
        if shell.build_opts.enableAddressSanitizer:
            cfg_env["CC"] += f" {CLANG_ASAN_PARAMS}"
            cfg_env["CXX"] += f" {CLANG_ASAN_PARAMS}"
        cfg_cmds.append("sh")
        cfg_cmds.append(str(shell.get_js_cfg_path()))
        cfg_cmds.append("--target=i686-pc-linux")
        if shell.build_opts.enableSimulatorArm32:
            # --enable-arm-simulator became --enable-simulator=arm in rev 25e99bc12482
            # but unknown flags are ignored, so we compile using both till Fx38 ESR is deprecated
            # Newer configure.in changes mean that things blow up if unknown/removed configure
            # options are entered, so specify it only if it's requested.
            if shell.build_opts.enableArmSimulatorObsolete:
                cfg_cmds.append("--enable-arm-simulator")
            cfg_cmds.append("--enable-simulator=arm")
    # 64-bit shell on Mac OS X 10.13 El Capitan and greater
    elif parse_version(platform.mac_ver()[0]) >= parse_version("10.13") and not shell.build_opts.enable32:
        cfg_env["CC"] = f"clang {CLANG_PARAMS}"
        cfg_env["CXX"] = f"clang++ {CLANG_PARAMS}"
        if shell.build_opts.enableAddressSanitizer:
            cfg_env["CC"] += f" {CLANG_ASAN_PARAMS}"
            cfg_env["CXX"] += f" {CLANG_ASAN_PARAMS}"
        if shutil.which("brew"):
            cfg_env["AUTOCONF"] = "/usr/local/Cellar/autoconf213/2.13/bin/autoconf213"
        cfg_cmds.append("sh")
        cfg_cmds.append(str(shell.get_js_cfg_path()))
        cfg_cmds.append("--target=x86_64-apple-darwin17.7.0")  # macOS 10.13.6
        cfg_cmds.append("--disable-xcode-checks")
        if shell.build_opts.enableSimulatorArm64:
            cfg_cmds.append("--enable-simulator=arm64")

    elif platform.system() == "Windows":
        win_mozbuild_clang_bin_path = WIN_MOZBUILD_CLANG_PATH / "bin"
        assert win_mozbuild_clang_bin_path.is_dir(), 'Please first run "./mach bootstrap".'
        assert (win_mozbuild_clang_bin_path / "clang.exe").is_file()
        assert (win_mozbuild_clang_bin_path / "llvm-config.exe").is_file()
        cfg_env["LIBCLANG_PATH"] = str(win_mozbuild_clang_bin_path)
        cfg_env["MAKE"] = "mozmake"  # Workaround for bug 948534
        if shell.build_opts.enableAddressSanitizer:
            cfg_env["CFLAGS"] = CLANG_ASAN_PARAMS
            cfg_env["CXXFLAGS"] = CLANG_ASAN_PARAMS
            cfg_env["LDFLAGS"] = ("clang_rt.asan_dynamic-x86_64.lib "
                                  "clang_rt.asan_dynamic_runtime_thunk-x86_64.lib")
            cfg_env["CLANG_LIB_DIR"] = str(WIN_MOZBUILD_CLANG_PATH / "lib" / "clang" / CLANG_VER / "lib" / "windows")
            cfg_env["MOZ_CLANG_RT_ASAN_LIB_PATH"] = f'{cfg_env["CLANG_LIB_DIR"]}/clang_rt.asan_dynamic-x86_64.dll'
            assert Path(cfg_env["MOZ_CLANG_RT_ASAN_LIB_PATH"]).is_file()
            cfg_env["LIB"] = cfg_env.get("LIB", "") + cfg_env["CLANG_LIB_DIR"]
        cfg_cmds.append("sh")
        cfg_cmds.append(str(shell.get_js_cfg_path()))
        if shell.build_opts.enable32:
            cfg_cmds.append("--host=x86_64-pc-mingw32")
            cfg_cmds.append("--target=i686-pc-mingw32")
            if shell.build_opts.enableSimulatorArm32:
                # --enable-arm-simulator became --enable-simulator=arm in rev 25e99bc12482
                # but unknown flags are ignored, so we compile using both till Fx38 ESR is deprecated
                # Newer configure.in changes mean that things blow up if unknown/removed configure
                # options are entered, so specify it only if it's requested.
                if shell.build_opts.enableArmSimulatorObsolete:
                    cfg_cmds.append("--enable-arm-simulator")
                cfg_cmds.append("--enable-simulator=arm")
        else:
            cfg_cmds.append("--host=x86_64-pc-mingw32")
            cfg_cmds.append("--target=x86_64-pc-mingw32")
            if shell.build_opts.enableSimulatorArm64:
                cfg_cmds.append("--enable-simulator=arm64")
    else:
        if shell.build_opts.enableAddressSanitizer:
            cfg_env["CC"] = f"clang {CLANG_PARAMS} {CLANG_ASAN_PARAMS}"
            cfg_env["CXX"] = f"clang++ {CLANG_PARAMS} {CLANG_ASAN_PARAMS}"
        cfg_cmds.append("sh")
        cfg_cmds.append(str(shell.get_js_cfg_path()))
        if shell.build_opts.enableSimulatorArm64:
            cfg_cmds.append("--enable-simulator=arm64")

    if shell.build_opts.enableDbg:
        cfg_cmds.append("--enable-debug")
    elif shell.build_opts.disableDbg:
        cfg_cmds.append("--disable-debug")

    if shell.build_opts.enableOpt:
        # pylint complains if this line uses an f-string with nested if-else, see https://git.io/fxfSo
        cfg_cmds.append("--enable-optimize" + ("=-O1" if shell.build_opts.enableValgrind else ""))
    elif shell.build_opts.disableOpt:
        cfg_cmds.append("--disable-optimize")
    if shell.build_opts.disableProfiling:
        cfg_cmds.append("--disable-profiling")

    if shell.build_opts.enableMoreDeterministic:
        # Fuzzing tweaks for more useful output, implemented in bug 706433
        cfg_cmds.append("--enable-more-deterministic")
    if shell.build_opts.enableOomBreakpoint:  # Extra debugging help for OOM assertions
        cfg_cmds.append("--enable-oom-breakpoint")
    if shell.build_opts.enableWithoutIntlApi:  # Speeds up compilation but is non-default
        cfg_cmds.append("--without-intl-api")

    if shell.build_opts.enableAddressSanitizer:
        cfg_cmds.append("--enable-address-sanitizer")
        cfg_cmds.append("--disable-jemalloc")
    if shell.build_opts.enableValgrind:
        cfg_cmds.append("--enable-valgrind")
        cfg_cmds.append("--disable-jemalloc")

    # We add the following flags by default.
    if os.name == "posix":
        cfg_cmds.append("--with-ccache")
    cfg_cmds.append("--enable-gczeal")
    cfg_cmds.append("--enable-debug-symbols")  # gets debug symbols on opt shells
    cfg_cmds.append("--disable-tests")

    # Disable cranelift if repository revision is on/after m-c rev 438680:4d9500ca5761edd678a109b6b5a4ac3f4aa5edb0, fx64
    # and before m-c rev 479295:9e7c1e1a993d51d611558244049a97599511e965, fx69
    if hg_helpers.existsAndIsAncestor(shell.get_repo_dir(), shell.get_hg_hash(),
                                      "9e7c1e1a993d51d611558244049a97599511e965") and not \
        hg_helpers.existsAndIsAncestor(shell.get_repo_dir(), shell.get_hg_hash(),
                                       "parents(4d9500ca5761edd678a109b6b5a4ac3f4aa5edb0)"):
        # if not hg_helpers.existsAndIsAncestor(shell.get_repo_dir(), shell.get_hg_hash(),
        #                                       "parents(4d9500ca5761edd678a109b6b5a4ac3f4aa5edb0)"):
        cfg_cmds.append("--disable-cranelift")

    if platform.system() == "Windows":
        # FIXME: Replace this with shlex's quote  # pylint: disable=fixme
        counter = 0
        for entry in cfg_cmds:
            if os.sep in entry:
                cfg_cmds[counter] = cfg_cmds[counter].replace(os.sep, "//")
            counter = counter + 1

    # Print whatever we added to the environment
    env_vars = []
    for env_var in set(cfg_env.keys()) - set(orig_cfg_env.keys()):
        str_to_be_appended = (
            f"{env_var}"
            f'="{cfg_env[str(env_var)]}'
            + '"' if " " in cfg_env[str(env_var)] else env_var +
            f"={cfg_env[str(env_var)]}"
        )
        env_vars.append(str_to_be_appended)
    sps.vdump(f'Command to be run is: {" ".join(quote(str(x)) for x in env_vars)} '
              f'{" ".join(quote(str(x)) for x in cfg_cmds)}')

    assert shell.get_js_objdir().is_dir()

    try:
        if platform.system() == "Windows":
            changed_cfg_cmds = []
            for entry in cfg_cmds:
                # For JS, quoted from :glandium: "the way icu subconfigure is called is what changed.
                #   but really, the whole thing likes forward slashes way better"
                # See bug 1038590 comment 9.
                if "\\" in entry:
                    entry = entry.replace("\\", "/")
                changed_cfg_cmds.append(entry)
            subprocess.run(changed_cfg_cmds,
                           check=True,
                           cwd=str(shell.get_js_objdir()),
                           env=cfg_env,
                           stderr=subprocess.STDOUT,
                           stdout=subprocess.PIPE).stdout.decode("utf-8", errors="replace")
        else:
            subprocess.run(cfg_cmds,
                           check=True,
                           cwd=str(shell.get_js_objdir()),
                           env=cfg_env,
                           stderr=subprocess.STDOUT,
                           stdout=subprocess.PIPE).stdout.decode("utf-8", errors="replace")
    except subprocess.CalledProcessError as ex:
        with io.open(str(shell.get_shell_cache_dir() / f"{shell.get_shell_name_without_ext()}.busted"), "a",
                     encoding="utf-8", errors="replace") as f:
            f.write(f"Configuration of {shell.get_repo_name()} rev {shell.get_hg_hash()} "
                    f"failed with the following output:\n")
            f.write(ex.stdout.decode("utf-8", errors="replace"))
        raise

    shell.set_env_added(env_vars)
    shell.set_env_full(cfg_env)
    shell.set_cfg_cmd_excl_env(cfg_cmds)


def sm_compile(shell):
    """Compile a binary and copy essential compiled files into a desired structure.

    Args:
        shell (object): SpiderMonkey shell parameters

    Raises:
        OSError: Raises when a compiled shell is absent

    Returns:
        Path: Path to the compiled shell
    """
    cmd_list = [MAKE_BINARY, "-C", str(shell.get_js_objdir()), f"-j{COMPILATION_JOBS}", "-s"]
    # Note that having a non-zero exit code does not mean that the operation did not succeed,
    # for example when compiling a shell. A non-zero exit code can appear even though a shell compiled successfully.
    # Thus, we should *not* use check=True here.
    out = subprocess.run(cmd_list,
                         cwd=str(shell.get_js_objdir()),
                         env=shell.get_env_full(),
                         stderr=subprocess.STDOUT,
                         stdout=subprocess.PIPE).stdout.decode("utf-8", errors="replace")

    if shell.get_shell_compiled_path().is_file():
        shutil.copy2(str(shell.get_shell_compiled_path()), str(shell.get_shell_cache_js_bin_path()))
        for run_lib in shell.get_shell_compiled_runlibs_path():
            if run_lib.is_file():
                shutil.copy2(str(run_lib), str(shell.get_shell_cache_dir()))
        if platform.system() == "Windows" and shell.build_opts.enableAddressSanitizer:
            shutil.copy2(str(WIN_MOZBUILD_CLANG_PATH / "lib" / "clang" / CLANG_VER / "lib" / "windows" /
                             "clang_rt.asan_dynamic-x86_64.dll"),
                         str(shell.get_shell_cache_dir()))

        shell.set_version(sm_compile_helpers.extract_vers(shell.get_js_objdir()))

        if platform.system() == "Linux":
            # Restrict this to only Linux for now. At least Mac OS X needs some (possibly *.a)
            # files in the objdir or else the stacks from failing testcases will lack symbols.
            shutil.rmtree(str(shell.get_shell_cache_dir() / "objdir-js"))
    else:
        if ((platform.system() == "Linux" or platform.system() == "Darwin") and
                ("internal compiler error: Killed (program cc1plus)" in out or  # GCC running out of memory
                 "error: unable to execute command: Killed" in out)):  # Clang running out of memory
            print("Trying once more due to the compiler running out of memory...")
            out = subprocess.run(cmd_list,
                                 cwd=str(shell.get_js_objdir()),
                                 env=shell.get_env_full(),
                                 stderr=subprocess.STDOUT,
                                 stdout=subprocess.PIPE).stdout.decode("utf-8", errors="replace")
        # A non-zero error can be returned during make, but eventually a shell still gets compiled.
        if shell.get_shell_compiled_path().is_file():
            print("A shell was compiled even though there was a non-zero exit code. Continuing...")
        else:
            print(f"{MAKE_BINARY} did not result in a js shell:")
            with io.open(str(shell.get_shell_cache_dir() / f"{shell.get_shell_name_without_ext()}.busted"), "a",
                         encoding="utf-8", errors="replace") as f:
                f.write(f"Compilation of {shell.get_repo_name()} rev {shell.get_hg_hash()} "
                        f"failed with the following output:\n")
                f.write(out)
            raise OSError(f"{MAKE_BINARY} did not result in a js shell.")

    return shell.get_shell_compiled_path()


def makeTestRev(options):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    def testRev(rev):  # pylint: disable=invalid-name,missing-return-doc,missing-return-type-doc
        shell = CompiledShell(options.build_options, rev)
        print(f"Rev {rev}:", end=" ")

        try:
            obtainShell(shell, updateToRev=rev)
        except (subprocess.CalledProcessError, OSError):
            return options.compilationFailedLabel, "compilation failed"

        print("Testing...", end=" ")
        return options.testAndLabel(shell.get_shell_cache_js_bin_path(), rev)
    return testRev


def obtainShell(shell, updateToRev=None, updateLatestTxt=False):  # pylint: disable=invalid-name,missing-param-doc
    # pylint: disable=missing-raises-doc,missing-type-doc,too-many-branches,too-complex,too-many-statements
    """Obtain a js shell. Keep the objdir for now, especially .a files, for symbols."""
    assert sm_compile_helpers.get_lock_dir_path(Path.home(), shell.build_opts.repo_dir).is_dir()
    cached_no_shell = shell.get_shell_cache_js_bin_path().with_suffix(".busted")

    if shell.get_shell_cache_js_bin_path().is_file():  # pylint: disable=no-else-return
        # Don't remove the comma at the end of this line, and thus remove the newline printed.
        # We would break JSBugMon.
        print("Found cached shell...")
        # Assuming that since the binary is present, everything else (e.g. symbols) is also present
        if platform.system() == "Windows":
            sm_compile_helpers.verify_full_win_pageheap(shell.get_shell_cache_js_bin_path())
        return
    elif cached_no_shell.is_file():
        raise OSError("Found a cached shell that failed compilation...")
    elif shell.get_shell_cache_dir().is_dir():
        print("Found a cache dir without a successful/failed shell...")
        file_system_helpers.rm_tree_incl_readonly_files(shell.get_shell_cache_dir())

    shell.get_shell_cache_dir().mkdir()
    hg_helpers.destroyPyc(shell.build_opts.repo_dir)

    s3cache_obj = s3cache.S3Cache(S3_SHELL_CACHE_DIRNAME)
    use_s3cache = s3cache_obj.connect()

    if use_s3cache:
        if s3cache_obj.downloadFile(f"{shell.get_shell_name_without_ext()}.busted",
                                    f"{shell.get_shell_cache_js_bin_path()}.busted"):
            raise OSError(f"Found a .busted file for rev {shell.get_hg_hash()}")

        if s3cache_obj.downloadFile(f"{shell.get_shell_name_without_ext()}.tar.bz2",
                                    str(shell.get_s3_tar_with_ext_full_path())):
            print("Extracting shell...")
            with tarfile.open(str(shell.get_s3_tar_with_ext_full_path()), "r") as f:
                f.extractall(str(shell.get_shell_cache_dir()))
            # Delete tarball after downloading from S3
            shell.get_s3_tar_with_ext_full_path().unlink()
            if platform.system() == "Windows":
                sm_compile_helpers.verify_full_win_pageheap(shell.get_shell_cache_js_bin_path())
            return

    try:
        if updateToRev:
            # Print *with* a trailing newline to avoid breaking other stuff
            print(f"Updating to rev {updateToRev} in the {shell.build_opts.repo_dir} repository...")
            subprocess.run(["hg", "-R", str(shell.build_opts.repo_dir),
                            "update", "-C", "-r", updateToRev],
                           check=True,
                           cwd=os.getcwd(),
                           stderr=subprocess.DEVNULL,
                           timeout=9999)
        if shell.build_opts.patch_file:
            hg_helpers.patch_hg_repo_with_mq(shell.build_opts.patch_file, shell.get_repo_dir())

        cfgJsCompile(shell)
        if platform.system() == "Windows":
            sm_compile_helpers.verify_full_win_pageheap(shell.get_shell_cache_js_bin_path())
    except KeyboardInterrupt:
        file_system_helpers.rm_tree_incl_readonly_files(shell.get_shell_cache_dir())
        raise
    except (subprocess.CalledProcessError, OSError) as ex:
        file_system_helpers.rm_tree_incl_readonly_files(shell.get_shell_cache_dir() / "objdir-js")
        if shell.get_shell_cache_js_bin_path().is_file():  # Switch to contextlib.suppress when we are fully on Python 3
            shell.get_shell_cache_js_bin_path().unlink()
        with io.open(str(cached_no_shell), "a", encoding="utf-8", errors="replace") as f:
            f.write(f"\nCaught exception {ex!r} ({ex})\n")
            f.write("Backtrace:\n")
            f.write(f"{traceback.format_exc()}\n")
        print(f"Compilation failed ({ex}) (details in {cached_no_shell})")

        if use_s3cache:
            s3cache_obj.uploadFileToS3(f"{shell.get_shell_cache_js_bin_path()}.busted")
        raise
    finally:
        if shell.build_opts.patch_file:
            hg_helpers.qpop_qrm_applied_patch(shell.build_opts.patch_file, shell.get_repo_dir())

    if use_s3cache:
        s3cache_obj.compressAndUploadDirTarball(str(shell.get_shell_cache_dir()),
                                                str(shell.get_s3_tar_with_ext_full_path()))
        if updateLatestTxt:
            # So js-dbg-64-dm-darwin-cdcd33fd6e39 becomes js-dbg-64-dm-darwin-latest.txt with
            # js-dbg-64-dm-darwin-cdcd33fd6e39 as its contents.
            txt_info = f'{"-".join(str(shell.get_s3_tar_name_with_ext()).split("-")[:-1] + ["latest"])}.txt'
            s3cache_obj.uploadStrToS3("", txt_info, str(shell.get_s3_tar_name_with_ext()))
        shell.get_s3_tar_with_ext_full_path().unlink()


def main():
    """Execute main() function in CompiledShell class."""
    sys.exit(CompiledShell.main())


if __name__ == "__main__":
    main()

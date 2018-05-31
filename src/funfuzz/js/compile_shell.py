# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Compiles SpiderMonkey shells on different platforms using various specified configuration parameters.
"""

from __future__ import absolute_import, print_function, unicode_literals  # isort:skip

from builtins import object  # pylint: disable=redefined-builtin
import copy
import io
import multiprocessing
from optparse import OptionParser  # pylint: disable=deprecated-module
import os
import platform
import shutil
import sys
import tarfile
import traceback

from pkg_resources import parse_version
from shellescape import quote
from whichcraft import which  # Once we are fully on Python 3.5+, whichcraft can be removed in favour of shutil.which

from . import build_options
from . import inspect_shell
from ..util import hg_helpers
from ..util import s3cache
from ..util import subprocesses as sps
from ..util.lock_dir import LockDir

if sys.version_info.major == 2:
    if os.name == "posix":
        import subprocess32 as subprocess  # pylint: disable=import-error
    from pathlib2 import Path
else:
    from pathlib import Path  # pylint: disable=import-error
    import subprocess

S3_SHELL_CACHE_DIRNAME = "shell-cache"  # Used by autobisectjs

if platform.system() == "Windows":
    MAKE_BINARY = "mozmake"
    CLANG_PARAMS = "-fallback"
    # CLANG_ASAN_PARAMS = "-fsanitize=address -Dxmalloc=myxmalloc"
    # Note that Windows ASan builds are still a work-in-progress
    CLANG_ASAN_PARAMS = ""
else:
    MAKE_BINARY = "make"
    CLANG_PARAMS = "-Qunused-arguments"
    # See https://bugzilla.mozilla.org/show_bug.cgi?id=935795#c3 for some of the following flags:
    # CLANG_ASAN_PARAMS = "-fsanitize=address -Dxmalloc=myxmalloc -mllvm -asan-stack=0"
    # The flags above seem to fix a problem not on the js shell.
    CLANG_ASAN_PARAMS = "-fsanitize=address -Dxmalloc=myxmalloc"
    SSE2_FLAGS = "-msse2 -mfpmath=sse"  # See bug 948321
    CLANG_X86_FLAG = "-arch i386"

if multiprocessing.cpu_count() > 2:
    COMPILATION_JOBS = multiprocessing.cpu_count() + 1
else:
    COMPILATION_JOBS = 3  # Other single/dual core computers


class CompiledShellError(Exception):
    """Error class unique to CompiledShell objects."""
    pass


class CompiledShell(object):  # pylint: disable=too-many-instance-attributes,too-many-public-methods
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
        self.addedEnv = ""  # pylint: disable=invalid-name
        self.fullEnv = ""  # pylint: disable=invalid-name
        self.js_cfg_file = ""  # pylint: disable=invalid-name

        self.jsMajorVersion = ""  # pylint: disable=invalid-name
        self.jsVersion = ""  # pylint: disable=invalid-name

    @classmethod
    def main(cls, args=None):  # pylint: disable=missing-docstring,missing-return-doc,missing-return-type-doc
        # logging.basicConfig(format="%(message)s", level=logging.INFO)

        try:
            return cls.run(args)

        except CompiledShellError as ex:
            print(repr(ex))
            # log.error(ex)
            return 1

    @staticmethod
    def run(argv=None):  # pylint: disable=missing-param-doc,missing-return-doc,missing-return-type-doc,missing-type-doc
        """Build a shell and place it in the autobisectjs cache."""
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
                               "(python -m funfuzz.js.build_options --help)")

        parser.add_option("-r", "--rev",
                          dest="revision",
                          help="Specify revision to build")

        options = parser.parse_args(argv)[0]
        options.build_opts = build_options.parse_shell_opts(options.build_opts)

        with LockDir(get_lock_dir_path(Path.home(), options.build_opts.repo_dir)):
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

    def setEnvAdded(self, addedEnv):  # pylint: disable=invalid-name,missing-docstring
        self.addedEnv = addedEnv

    def getEnvAdded(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
        return self.addedEnv

    def setEnvFull(self, fullEnv):  # pylint: disable=invalid-name,missing-docstring
        self.fullEnv = fullEnv

    def getEnvFull(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
        return self.fullEnv

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

    def getRepoName(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
        return hg_helpers.hgrc_repo_name(self.build_opts.repo_dir)

    def getS3TarballWithExt(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc
        return self.get_shell_name_without_ext() + ".tar.bz2"

    def get_s3_tar_with_ext_full_path(self):
        """Retrieve the path to the tarball downloaded from S3.

        Returns:
            Path: Full path to the tarball in the local shell cache directory
        """
        return ensure_cache_dir(Path.home()) / self.getS3TarballWithExt()

    def get_shell_cache_dir(self):
        """Retrieve the shell cache directory of the intended js binary.

        Returns:
            Path: Full path to the shell cache directory of the intended js binary
        """
        return ensure_cache_dir(Path.home()) / self.get_shell_name_without_ext()

    def get_shell_cache_js_bin_path(self):
        """Retrieve the full path to the js binary located in the shell cache.

        Returns:
            Path: Full path to the js binary in the shell cache
        """
        return ensure_cache_dir(Path.home()) / self.get_shell_name_without_ext() / self.get_shell_name_with_ext()

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
        return self.shell_name_without_ext + (".exe" if platform.system() == "Windows" else "")

    def get_shell_name_without_ext(self):
        """Retrieve the name of the compiled js shell without the file extension.

        Returns:
            str: Name of the compiled js shell without the file extension
        """
        return self.shell_name_without_ext

    # Version numbers
    def getMajorVersion(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc
        return self.jsMajorVersion

    def setMajorVersion(self, jsMajorVersion):  # pylint: disable=invalid-name,missing-docstring
        self.jsMajorVersion = jsMajorVersion

    def getVersion(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
        return self.jsVersion

    def setVersion(self, jsVersion):  # pylint: disable=invalid-name,missing-docstring
        self.jsVersion = jsVersion


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
        autoconf213_mac_bin = "/usr/local/Cellar/autoconf213/2.13/bin/autoconf213" if which("brew") else "autoconf213"
        # Total hack to support new and old Homebrew configs, we can probably just call autoconf213
        if not Path(autoconf213_mac_bin).is_file():
            autoconf213_mac_bin = "autoconf213"
        subprocess.check_call([autoconf213_mac_bin], cwd=str(working_dir))
    elif platform.system() == "Linux":
        if which("autoconf2.13"):
            subprocess.run(["autoconf2.13"], check=True, cwd=str(working_dir))
        elif which("autoconf-2.13"):
            subprocess.run(["autoconf-2.13"], check=True, cwd=str(working_dir))
        elif which("autoconf213"):
            subprocess.run(["autoconf213"], check=True, cwd=str(working_dir))
    elif platform.system() == "Windows":
        # Windows needs to call sh to be able to find autoconf.
        subprocess.check_call(["sh", "autoconf-2.13"], cwd=str(working_dir))


def cfgJsCompile(shell):  # pylint: disable=invalid-name,missing-param-doc,missing-raises-doc,missing-type-doc
    """Configures, compiles and copies a js shell according to required parameters."""
    print("Compiling...")  # Print *with* a trailing newline to avoid breaking other stuff
    js_objdir_path = shell.get_shell_cache_dir() / "objdir-js"
    js_objdir_path.mkdir()
    shell.set_js_objdir(js_objdir_path)

    autoconf_run(shell.get_repo_dir() / "js" / "src")
    configure_try_count = 0
    while True:
        try:
            cfgBin(shell)
            break
        except Exception as ex:  # pylint: disable=broad-except
            configure_try_count += 1
            if configure_try_count > 3:
                print("Configuration of the js binary failed 3 times.")
                raise
            # This exception message is returned from sps.captureStdout via cfgBin.
            # No idea why this is platform.system() == "Linux" as well..
            if platform.system() == "Linux" or (platform.system() == "Windows" and
                                                "Windows conftest.exe configuration permission" in repr(ex)):
                print("Trying once more...")
                continue
    compileJs(shell)
    inspect_shell.verifyBinary(shell)

    compile_log = shell.get_shell_cache_dir() / (shell.get_shell_name_without_ext() + ".fuzzmanagerconf")
    if not compile_log.is_file():
        envDump(shell, compile_log)


def cfgBin(shell):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc,too-complex,too-many-branches
    # pylint: disable=too-many-statements
    """Configure a binary according to required parameters."""
    cfg_cmds = []
    cfg_env = copy.deepcopy(os.environ)
    orig_cfg_env = copy.deepcopy(os.environ)
    cfg_env["AR"] = "ar"
    if shell.build_opts.enable32 and platform.system() == "Linux":
        # 32-bit shell on 32/64-bit x86 Linux
        cfg_env["PKG_CONFIG_LIBDIR"] = "/usr/lib/pkgconfig"
        if shell.build_opts.buildWithClang:
            cfg_env["CC"] = cfg_env["HOST_CC"] = str(
                "clang %s %s %s" % (CLANG_PARAMS, SSE2_FLAGS, CLANG_X86_FLAG))
            cfg_env["CXX"] = cfg_env["HOST_CXX"] = str(
                "clang++ %s %s %s" % (CLANG_PARAMS, SSE2_FLAGS, CLANG_X86_FLAG))
        else:
            # apt-get `lib32z1 gcc-multilib g++-multilib` first, if on 64-bit Linux.
            cfg_env["CC"] = "gcc -m32 %s" % SSE2_FLAGS
            cfg_env["CXX"] = "g++ -m32 %s" % SSE2_FLAGS
        if shell.build_opts.buildWithAsan:
            cfg_env["CC"] += " " + CLANG_ASAN_PARAMS
            cfg_env["CXX"] += " " + CLANG_ASAN_PARAMS
        cfg_cmds.append("sh")
        cfg_cmds.append(str(shell.get_js_cfg_path()))
        cfg_cmds.append("--target=i686-pc-linux")
        if shell.build_opts.buildWithAsan:
            cfg_cmds.append("--enable-address-sanitizer")
        if shell.build_opts.enableSimulatorArm32:
            # --enable-arm-simulator became --enable-simulator=arm in rev 25e99bc12482
            # but unknown flags are ignored, so we compile using both till Fx38 ESR is deprecated
            # Newer configure.in changes mean that things blow up if unknown/removed configure
            # options are entered, so specify it only if it's requested.
            if shell.build_opts.enableArmSimulatorObsolete:
                cfg_cmds.append("--enable-arm-simulator")
            cfg_cmds.append("--enable-simulator=arm")
    # 64-bit shell on Mac OS X 10.11 El Capitan and greater
    elif parse_version(platform.mac_ver()[0]) >= parse_version("10.11") and not shell.build_opts.enable32:
        cfg_env["CC"] = "clang " + CLANG_PARAMS
        cfg_env["CXX"] = "clang++ " + CLANG_PARAMS
        if shell.build_opts.buildWithAsan:
            cfg_env["CC"] += " " + CLANG_ASAN_PARAMS
            cfg_env["CXX"] += " " + CLANG_ASAN_PARAMS
        if which("brew"):
            cfg_env["AUTOCONF"] = "/usr/local/Cellar/autoconf213/2.13/bin/autoconf213"
        cfg_cmds.append("sh")
        cfg_cmds.append(str(shell.get_js_cfg_path()))
        cfg_cmds.append("--target=x86_64-apple-darwin15.6.0")  # El Capitan 10.11.6
        cfg_cmds.append("--disable-xcode-checks")
        if shell.build_opts.buildWithAsan:
            cfg_cmds.append("--enable-address-sanitizer")
        if shell.build_opts.enableSimulatorArm64:
            cfg_cmds.append("--enable-simulator=arm64")

    elif platform.system() == "Windows":
        cfg_env["MAKE"] = "mozmake"  # Workaround for bug 948534
        if shell.build_opts.buildWithClang:
            cfg_env["CC"] = "clang-cl.exe " + CLANG_PARAMS
            cfg_env["CXX"] = "clang-cl.exe " + CLANG_PARAMS
        if shell.build_opts.buildWithAsan:
            cfg_env["CFLAGS"] = CLANG_ASAN_PARAMS
            cfg_env["CXXFLAGS"] = CLANG_ASAN_PARAMS
            cfg_env["LDFLAGS"] = ("clang_rt.asan_dynamic-x86_64.lib "
                                  "clang_rt.asan_dynamic_runtime_thunk-x86_64.lib "
                                  "clang_rt.asan_dynamic-x86_64.dll")
            cfg_env["HOST_CFLAGS"] = " "
            cfg_env["HOST_CXXFLAGS"] = " "
            cfg_env["HOST_LDFLAGS"] = " "
            cfg_env["LIB"] += r"C:\Program Files\LLVM\lib\clang\4.0.0\lib\windows"
        cfg_cmds.append("sh")
        cfg_cmds.append(str(shell.get_js_cfg_path()))
        if shell.build_opts.enable32:
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
        if shell.build_opts.buildWithAsan:
            cfg_cmds.append("--enable-address-sanitizer")
    else:
        # We might still be using GCC on Linux 64-bit, so do not use clang unless Asan is specified
        if shell.build_opts.buildWithClang:
            cfg_env["CC"] = "clang " + CLANG_PARAMS
            cfg_env["CXX"] = "clang++ " + CLANG_PARAMS
        if shell.build_opts.buildWithAsan:
            cfg_env["CC"] += " " + CLANG_ASAN_PARAMS
            cfg_env["CXX"] += " " + CLANG_ASAN_PARAMS
        cfg_cmds.append("sh")
        cfg_cmds.append(str(shell.get_js_cfg_path()))
        if shell.build_opts.buildWithAsan:
            cfg_cmds.append("--enable-address-sanitizer")

    if shell.build_opts.buildWithClang:
        if platform.system() == "Windows":
            assert "clang-cl" in cfg_env["CC"]
            assert "clang-cl" in cfg_env["CXX"]
        else:
            assert "clang" in cfg_env["CC"]
            assert "clang++" in cfg_env["CXX"]
        cfg_cmds.append("--disable-jemalloc")  # See bug 1146895

    if shell.build_opts.enableDbg:
        cfg_cmds.append("--enable-debug")
    elif shell.build_opts.disableDbg:
        cfg_cmds.append("--disable-debug")

    if shell.build_opts.enableOpt:
        cfg_cmds.append("--enable-optimize" + ("=-O1" if shell.build_opts.buildWithVg else ""))
    elif shell.build_opts.disableOpt:
        cfg_cmds.append("--disable-optimize")
    if shell.build_opts.enableProfiling:  # Now obsolete, retained for backward compatibility
        cfg_cmds.append("--enable-profiling")
    if shell.build_opts.disableProfiling:
        cfg_cmds.append("--disable-profiling")

    if shell.build_opts.enableMoreDeterministic:
        # Fuzzing tweaks for more useful output, implemented in bug 706433
        cfg_cmds.append("--enable-more-deterministic")
    if shell.build_opts.enableOomBreakpoint:  # Extra debugging help for OOM assertions
        cfg_cmds.append("--enable-oom-breakpoint")
    if shell.build_opts.enableWithoutIntlApi:  # Speeds up compilation but is non-default
        cfg_cmds.append("--without-intl-api")

    if shell.build_opts.buildWithVg:
        cfg_cmds.append("--enable-valgrind")
        cfg_cmds.append("--disable-jemalloc")

    # We add the following flags by default.
    if os.name == "posix":
        cfg_cmds.append("--with-ccache")
    cfg_cmds.append("--enable-gczeal")
    cfg_cmds.append("--enable-debug-symbols")  # gets debug symbols on opt shells
    cfg_cmds.append("--disable-tests")

    if platform.system() == "Windows":
        # FIXME: Replace this with shellescape's quote  # pylint: disable=fixme
        counter = 0
        for entry in cfg_cmds:
            if os.sep in entry:
                cfg_cmds[counter] = cfg_cmds[counter].replace(os.sep, "//")
            counter = counter + 1

    # Print whatever we added to the environment
    env_vars = []
    for env_var in set(cfg_env.keys()) - set(orig_cfg_env.keys()):
        str_to_be_appended = str(env_var + '="' + cfg_env[str(env_var)] +
                                 '"' if " " in cfg_env[str(env_var)] else env_var +
                                 "=" + cfg_env[str(env_var)])
        env_vars.append(str_to_be_appended)
    sps.vdump("Command to be run is: " + " ".join(quote(str(x)) for x in env_vars) + " " +
              " ".join(quote(str(x)) for x in cfg_cmds))

    assert shell.get_js_objdir().is_dir()

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

    # We could save the stdout here into a file if it throws

    shell.setEnvAdded(env_vars)
    shell.setEnvFull(cfg_env)
    shell.set_cfg_cmd_excl_env(cfg_cmds)


def compileJs(shell):  # pylint: disable=invalid-name,missing-param-doc,missing-raises-doc,missing-type-doc
    """Compile and copy a binary."""
    try:
        cmd_list = [MAKE_BINARY, "-C", str(shell.get_js_objdir()), "-j" + str(COMPILATION_JOBS), "-s"]
        out = subprocess.run(cmd_list,
                             cwd=str(shell.get_js_objdir()),
                             env=shell.getEnvFull(),
                             stderr=subprocess.STDOUT,
                             stdout=subprocess.PIPE).stdout.decode("utf-8", errors="replace")
    except Exception as ex:  # pylint: disable=broad-except
        # This exception message is returned from sps.captureStdout via cmd_list.
        if (platform.system() == "Linux" or platform.system() == "Darwin") and \
                ("GCC running out of memory" in repr(ex) or "Clang running out of memory" in repr(ex)):
            # FIXME: Absolute hack to retry after hitting OOM.  # pylint: disable=fixme
            print("Trying once more due to the compiler running out of memory...")
            out = subprocess.run(cmd_list,
                                 cwd=str(shell.get_js_objdir()),
                                 env=shell.getEnvFull(),
                                 stderr=subprocess.STDOUT,
                                 stdout=subprocess.PIPE).stdout.decode("utf-8", errors="replace")
        # A non-zero error can be returned during make, but eventually a shell still gets compiled.
        if shell.get_shell_compiled_path().is_file():
            print("A shell was compiled even though there was a non-zero exit code. Continuing...")
        else:
            print("%s did not result in a js shell:" % MAKE_BINARY.decode("utf-8", errors="replace"))
            raise

    # We could save the stdout here into a file if it throws

    if shell.get_shell_compiled_path().is_file():
        shutil.copy2(str(shell.get_shell_compiled_path()), str(shell.get_shell_cache_js_bin_path()))
        for run_lib in shell.get_shell_compiled_runlibs_path():
            if run_lib.is_file():
                shutil.copy2(str(run_lib), str(shell.get_shell_cache_dir()))

        version = extract_vers(shell.get_js_objdir())
        shell.setMajorVersion(version.split(".")[0])
        shell.setVersion(version)

        if platform.system() == "Linux":
            # Restrict this to only Linux for now. At least Mac OS X needs some (possibly *.a)
            # files in the objdir or else the stacks from failing testcases will lack symbols.
            shutil.rmtree(str(shell.get_shell_cache_dir() / "objdir-js"))
    else:
        print(out.decode("utf-8", errors="replace"))
        raise Exception(MAKE_BINARY + " did not result in a js shell, no exception thrown.")


def createBustedFile(filename, e):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc
    """Create a .busted file with the exception message and backtrace included."""
    with open(str(filename), "w") as f:
        f.write("Caught exception %r (%s)\n" % (e, e))
        f.write("Backtrace:\n")
        f.write(traceback.format_exc() + "\n")

    print("Compilation failed (%s) (details in %s)" % (e, filename))


def envDump(shell, log):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc
    """Dump environment to a .fuzzmanagerconf file."""
    # Platform and OS detection for the spec, part of which is in:
    #   https://wiki.mozilla.org/Security/CrashSignatures
    fmconf_platform = "x86" if shell.build_opts.enable32 else "x86-64"

    if platform.system() == "Linux":
        fmconf_os = "linux"
    elif platform.system() == "Darwin":
        fmconf_os = "macosx"
    elif platform.system() == "Windows":
        fmconf_os = "windows"

    with open(str(log), "a") as f:
        f.write("# Information about shell:\n# \n")

        f.write("# Create another shell in shell-cache like this one:\n")
        f.write('# python -u -m %s -b "%s" -r %s\n# \n' % ("funfuzz.js.compile_shell",
                                                           shell.build_opts.build_options_str, shell.get_hg_hash()))

        f.write("# Full environment is:\n")
        f.write("# %s\n# \n" % str(shell.getEnvFull()))

        f.write("# Full configuration command with needed environment variables is:\n")
        f.write("# %s %s\n# \n" % (" ".join(quote(str(x)) for x in shell.getEnvAdded()),
                                   " ".join(quote(str(x)) for x in shell.get_cfg_cmd_excl_env())))

        # .fuzzmanagerconf details
        f.write("\n")
        f.write("[Main]\n")
        f.write("platform = %s\n" % fmconf_platform)
        f.write("product = %s\n" % shell.getRepoName())
        f.write("product_version = %s\n" % shell.get_hg_hash())
        f.write("os = %s\n" % fmconf_os)

        f.write("\n")
        f.write("[Metadata]\n")
        f.write("buildFlags = %s\n" % shell.build_opts.build_options_str)
        f.write("majorVersion = %s\n" % shell.getMajorVersion())
        f.write("pathPrefix = %s/\n" % shell.get_repo_dir())
        f.write("version = %s\n" % shell.getVersion())


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
    lockdir_name = "shell-%s-lock" % repo_dir.name
    if tbox_id:
        lockdir_name += "-%s" % tbox_id
    return ensure_cache_dir(cache_dir_base) / lockdir_name


def makeTestRev(options):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    def testRev(rev):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
        shell = CompiledShell(options.build_options, rev)
        print("Rev %s:" % rev.decode("utf-8", errors="replace"), end=" ")

        try:
            obtainShell(shell, updateToRev=rev)
        except Exception:  # pylint: disable=broad-except
            return (options.compilationFailedLabel, "compilation failed")

        print("Testing...", end=" ")
        return options.testAndLabel(shell.get_shell_cache_js_bin_path(), rev)
    return testRev


def obtainShell(shell, updateToRev=None, updateLatestTxt=False):  # pylint: disable=invalid-name,missing-param-doc
    # pylint: disable=missing-raises-doc,missing-type-doc,too-many-branches,too-complex,too-many-statements
    """Obtain a js shell. Keep the objdir for now, especially .a files, for symbols."""
    assert get_lock_dir_path(Path.home(), shell.build_opts.repo_dir).is_dir()
    cached_no_shell = shell.get_shell_cache_js_bin_path().with_suffix(".busted")

    if shell.get_shell_cache_js_bin_path().is_file():
        # Don't remove the comma at the end of this line, and thus remove the newline printed.
        # We would break JSBugMon.
        print("Found cached shell...")
        # Assuming that since the binary is present, everything else (e.g. symbols) is also present
        if platform.system() == "Windows":
            verify_full_win_pageheap(shell.get_shell_cache_js_bin_path())
        return
    elif cached_no_shell.is_file():
        raise Exception("Found a cached shell that failed compilation...")
    elif shell.get_shell_cache_dir().is_dir():
        print("Found a cache dir without a successful/failed shell...")
        sps.rm_tree_incl_readonly(shell.get_shell_cache_dir())

    shell.get_shell_cache_dir().mkdir()
    hg_helpers.destroyPyc(shell.build_opts.repo_dir)

    s3cache_obj = s3cache.S3Cache(S3_SHELL_CACHE_DIRNAME)
    use_s3cache = s3cache_obj.connect()

    if use_s3cache:
        if s3cache_obj.downloadFile(str(shell.get_shell_name_without_ext() + ".busted"),
                                    str(shell.get_shell_cache_js_bin_path()) + ".busted"):
            raise Exception("Found a .busted file for rev " + shell.get_hg_hash())

        if s3cache_obj.downloadFile(str(shell.get_shell_name_without_ext() + ".tar.bz2"),
                                    str(shell.get_s3_tar_with_ext_full_path())):
            print("Extracting shell...")
            with tarfile.open(str(shell.get_s3_tar_with_ext_full_path()), "r") as f:
                f.extractall(str(shell.get_shell_cache_dir()))
            # Delete tarball after downloading from S3
            shell.get_s3_tar_with_ext_full_path().unlink()
            if platform.system() == "Windows":
                verify_full_win_pageheap(shell.get_shell_cache_js_bin_path())
            return

    try:
        if updateToRev:
            # Print *with* a trailing newline to avoid breaking other stuff
            print("Updating to rev %s in the %s repository..." % (
                updateToRev.decode("utf-8", errors="replace"),
                shell.build_opts.repo_dir.decode("utf-8", errors="replace")))
            subprocess.run(["hg", "-R", shell.build_opts.repo_dir, "update", "-C", "-r", updateToRev],
                           check=True,
                           # pylint: disable=no-member
                           cwd=os.getcwdu() if sys.version_info.major == 2 else os.getcwd(),
                           stderr=subprocess.DEVNULL,
                           timeout=999)
        if shell.build_opts.patch_file:
            hg_helpers.patch_hg_repo_with_mq(shell.build_opts.patch_file, shell.get_repo_dir())

        cfgJsCompile(shell)
        if platform.system() == "Windows":
            verify_full_win_pageheap(shell.get_shell_cache_js_bin_path())
    except KeyboardInterrupt:
        sps.rm_tree_incl_readonly(shell.get_shell_cache_dir())
        raise
    except Exception as ex:
        # Remove the cache dir, but recreate it with only the .busted file.
        sps.rm_tree_incl_readonly(shell.get_shell_cache_dir())
        shell.get_shell_cache_dir().mkdir()
        createBustedFile(cached_no_shell, ex)
        if use_s3cache:
            s3cache_obj.uploadFileToS3(str(shell.get_shell_cache_js_bin_path()) + ".busted")
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
            txt_info = "-".join(str(shell.getS3TarballWithExt()).split("-")[:-1] + ["latest"]) + ".txt"
            s3cache_obj.uploadStrToS3("", txt_info, str(shell.getS3TarballWithExt()))
        shell.get_s3_tar_with_ext_full_path().unlink()


def verify_full_win_pageheap(shell_path):
    """Turn on full page heap verification on Windows.

    Args:
        shell_path (Path): Path to the compiled js shell
    """
    # More info: https://msdn.microsoft.com/en-us/library/windows/hardware/ff543097(v=vs.85).aspx
    # or https://blogs.msdn.microsoft.com/webdav_101/2010/06/22/detecting-heap-corruption-using-gflags-and-dumps/
    gflags_bin_path = Path(os.getenv("PROGRAMW6432")) / "Debugging Tools for Windows (x64)" / "gflags.exe"
    if gflags_bin_path.is_file() and shell_path.is_file():  # pylint: disable=no-member
        print(subprocess.check_output([str(gflags_bin_path).decode("utf-8", errors="replace"),
                                       "-p", "/enable", shell_path.decode("utf-8", errors="replace"), "/full"]))


def main():
    """Execute main() function in CompiledShell class."""
    exit(CompiledShell.main())


if __name__ == "__main__":
    main()

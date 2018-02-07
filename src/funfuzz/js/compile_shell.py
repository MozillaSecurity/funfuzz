# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Compiles SpiderMonkey shells on different platforms using various specified configuration parameters.
"""

from __future__ import absolute_import, print_function, unicode_literals

import copy
import ctypes
import io
import multiprocessing
import os
import shutil
import subprocess
import sys
import tarfile
import traceback
from optparse import OptionParser  # pylint: disable=deprecated-module

from . import build_options
from . import inspect_shell
from ..util import hg_helpers
from ..util import s3cache
from ..util import subprocesses as sps
from ..util.lock_dir import LockDir

S3_SHELL_CACHE_DIRNAME = 'shell-cache'  # Used by autoBisect

if sps.isWin:
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


class CompiledShell(object):  # pylint: disable=missing-docstring,too-many-instance-attributes,too-many-public-methods
    def __init__(self, buildOpts, hgHash):
        self.shellNameWithoutExt = build_options.computeShellName(buildOpts, hgHash)  # pylint: disable=invalid-name
        self.hgHash = hgHash  # pylint: disable=invalid-name
        self.build_opts = buildOpts

        self.jsObjdir = ''  # pylint: disable=invalid-name

        self.cfg = ''
        self.destDir = ''  # pylint: disable=invalid-name
        self.addedEnv = ""  # pylint: disable=invalid-name
        self.fullEnv = ""  # pylint: disable=invalid-name
        self.jsCfgFile = ''  # pylint: disable=invalid-name

        self.jsMajorVersion = ''  # pylint: disable=invalid-name
        self.jsVersion = ''  # pylint: disable=invalid-name

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
        """Build a shell and place it in the autoBisect cache."""
        usage = 'Usage: %prog [options]'
        parser = OptionParser(usage)
        parser.disable_interspersed_args()

        parser.set_defaults(
            build_opts="",
        )

        # Specify how the shell will be built.
        parser.add_option('-b', '--build',
                          dest='build_opts',
                          help="Specify build options, e.g. -b '--disable-debug --enable-optimize' "
                               "(python -m funfuzz.js.build_options --help)")

        parser.add_option('-r', '--rev',
                          dest='revision',
                          help='Specify revision to build')

        options = parser.parse_args(argv)[0]
        options.build_opts = build_options.parseShellOptions(options.build_opts)

        with LockDir(getLockDirPath(options.build_opts.repoDir)):
            if options.revision:
                shell = CompiledShell(options.build_opts, options.revision)
            else:
                local_orig_hg_hash = hg_helpers.getRepoHashAndId(options.build_opts.repoDir)[0]
                shell = CompiledShell(options.build_opts, local_orig_hg_hash)

            obtainShell(shell, updateToRev=options.revision)
            print(shell.getShellCacheFullPath())

        return 0

    def getCfgCmdExclEnv(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc
        return self.cfg

    def setCfgCmdExclEnv(self, cfg):  # pylint: disable=invalid-name,missing-docstring
        self.cfg = cfg

    def setEnvAdded(self, addedEnv):  # pylint: disable=invalid-name,missing-docstring
        self.addedEnv = addedEnv

    def getEnvAdded(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
        return self.addedEnv

    def setEnvFull(self, fullEnv):  # pylint: disable=invalid-name,missing-docstring
        self.fullEnv = fullEnv

    def getEnvFull(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
        return self.fullEnv

    def getHgHash(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
        return self.hgHash

    def getJsCfgPath(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
        self.jsCfgFile = sps.normExpUserPath(os.path.join(self.getRepoDirJsSrc(), 'configure'))
        assert os.path.isfile(self.jsCfgFile)
        return self.jsCfgFile

    def getJsObjdir(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
        return self.jsObjdir

    def setJsObjdir(self, oDir):  # pylint: disable=invalid-name,missing-docstring
        self.jsObjdir = oDir

    def getRepoDir(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
        return self.build_opts.repoDir

    def getRepoDirJsSrc(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc
        return sps.normExpUserPath(os.path.join(self.getRepoDir(), 'js', 'src'))

    def getRepoName(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
        return hg_helpers.getRepoNameFromHgrc(self.build_opts.repoDir)

    def getS3TarballWithExt(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc
        return self.getShellNameWithoutExt() + '.tar.bz2'

    def getS3TarballWithExtFullPath(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc
        return sps.normExpUserPath(os.path.join(ensureCacheDir(), self.getS3TarballWithExt()))

    def getShellCacheDir(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc
        return sps.normExpUserPath(os.path.join(ensureCacheDir(), self.getShellNameWithoutExt()))

    def getShellCacheFullPath(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc
        return sps.normExpUserPath(os.path.join(self.getShellCacheDir(), self.getShellNameWithExt()))

    def getShellCompiledPath(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc
        return sps.normExpUserPath(
            os.path.join(self.getJsObjdir(), 'dist', 'bin', 'js' + ('.exe' if sps.isWin else '')))

    def getShellCompiledRunLibsPath(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc
        libs_list = [
            sps.normExpUserPath(os.path.join(self.getJsObjdir(), 'dist', 'bin', runLib))
            for runLib in inspect_shell.ALL_RUN_LIBS
        ]
        return libs_list

    def getShellNameWithExt(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc
        return self.shellNameWithoutExt + (".exe" if sps.isWin else "")

    def getShellNameWithoutExt(self):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
        # pylint: disable=missing-return-type-doc
        return self.shellNameWithoutExt

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


def ensureCacheDir():  # pylint: disable=invalid-name,missing-return-doc,missing-return-type-doc
    """Return a cache directory for compiled shells to live in, and create one if needed."""
    cache_dir = os.path.join(sps.normExpUserPath('~'), 'shell-cache')
    ensureDir(cache_dir)

    # Expand long Windows paths (overcome legacy MS-DOS 8.3 stuff)
    # This has to occur after the shell-cache directory is created
    if sps.isWin:  # adapted from http://stackoverflow.com/a/3931799
        if sys.version_info.major == 2:
            utext = unicode   # noqa pylint: disable=redefined-builtin,undefined-variable,unicode-builtin
        else:
            utext = str
        win_temp_dir = utext(cache_dir)
        get_long_path_name = ctypes.windll.kernel32.GetLongPathNameW
        unicode_buf = ctypes.create_unicode_buffer(get_long_path_name(win_temp_dir, 0, 0))
        get_long_path_name(win_temp_dir, unicode_buf, len(unicode_buf))
        cache_dir = sps.normExpUserPath(str(unicode_buf.value))  # convert back to a str

    return cache_dir


def ensureDir(directory):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc
    """Create a directory, if it does not already exist."""
    if not os.path.exists(directory):
        os.mkdir(directory)
    assert os.path.isdir(directory)


def autoconfRun(cwDir):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc
    """Run autoconf binaries corresponding to the platform."""
    if sps.isMac:
        if subprocess.check_call(["which", "brew"], stdout=subprocess.PIPE):
            autoconf213_mac_bin = "/usr/local/Cellar/autoconf213/2.13/bin/autoconf213"
        else:
            autoconf213_mac_bin = "autoconf213"
        # Total hack to support new and old Homebrew configs, we can probably just call autoconf213
        if not os.path.isfile(sps.normExpUserPath(autoconf213_mac_bin)):
            autoconf213_mac_bin = 'autoconf213'
        subprocess.check_call([autoconf213_mac_bin], cwd=cwDir)
    elif sps.isLinux:
        # FIXME: We should use a method that is similar to the client.mk one, as per  # pylint: disable=fixme
        #   https://github.com/MozillaSecurity/funfuzz/issues/9
        try:
            # Ubuntu
            subprocess.check_call(['autoconf2.13'], cwd=cwDir)
        except OSError:
            # Fedora has a different name
            subprocess.check_call(['autoconf-2.13'], cwd=cwDir)
    elif sps.isWin:
        # Windows needs to call sh to be able to find autoconf.
        subprocess.check_call(['sh', 'autoconf-2.13'], cwd=cwDir)


def cfgJsCompile(shell):  # pylint: disable=invalid-name,missing-param-doc,missing-raises-doc,missing-type-doc
    """Configures, compiles and copies a js shell according to required parameters."""
    print("Compiling...")  # Print *with* a trailing newline to avoid breaking other stuff
    os.mkdir(sps.normExpUserPath(os.path.join(shell.getShellCacheDir(), 'objdir-js')))
    shell.setJsObjdir(sps.normExpUserPath(os.path.join(shell.getShellCacheDir(), 'objdir-js')))

    autoconfRun(shell.getRepoDirJsSrc())
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
            # No idea why this is sps.isLinux as well..
            if sps.isLinux or (sps.isWin and 'Windows conftest.exe configuration permission' in repr(ex)):
                print("Trying once more...")
                continue
    compileJs(shell)
    inspect_shell.verifyBinary(shell)

    compile_log = sps.normExpUserPath(os.path.join(shell.getShellCacheDir(),
                                                   shell.getShellNameWithoutExt() + '.fuzzmanagerconf'))
    if not os.path.isfile(compile_log):
        envDump(shell, compile_log)


def cfgBin(shell):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc,too-complex,too-many-branches
    # pylint: disable=too-many-statements
    """Configure a binary according to required parameters."""
    cfg_cmds = []
    cfg_env = copy.deepcopy(os.environ)
    orig_cfg_env = copy.deepcopy(os.environ)
    cfg_env["AR"] = "ar"
    if shell.build_opts.enable32 and os.name == "posix":
        # 32-bit shell on Mac OS X 10.11 El Capitan and greater
        if sps.isMac:
            assert sps.macVer() >= [10, 11]  # We no longer support 10.10 Yosemite and prior.
            # Uses system clang
            cfg_env["CC"] = cfg_env["HOST_CC"] = "clang %s %s" % (CLANG_PARAMS, SSE2_FLAGS)
            cfg_env["CXX"] = cfg_env["HOST_CXX"] = "clang++ %s %s" % (CLANG_PARAMS, SSE2_FLAGS)
            if shell.build_opts.buildWithAsan:
                cfg_env["CC"] += " " + CLANG_ASAN_PARAMS
                cfg_env["CXX"] += " " + CLANG_ASAN_PARAMS
            cfg_env["CC"] += " " + CLANG_X86_FLAG  # only needed for CC, not HOST_CC
            cfg_env["CXX"] += " " + CLANG_X86_FLAG  # only needed for CXX, not HOST_CXX
            cfg_env["RANLIB"] = "ranlib"
            cfg_env["AS"] = "$CC"
            cfg_env["LD"] = "ld"
            cfg_env["STRIP"] = "strip -x -S"
            cfg_env["CROSS_COMPILE"] = "1"
            if subprocess.check_call(["which", "brew"], stdout=subprocess.PIPE):
                cfg_env["AUTOCONF"] = "/usr/local/Cellar/autoconf213/2.13/bin/autoconf213"
                # Hacked up for new and old Homebrew configs, we can probably just call autoconf213
                if not os.path.isfile(sps.normExpUserPath(cfg_env["AUTOCONF"])):
                    cfg_env["AUTOCONF"] = "autoconf213"
            cfg_cmds.append('sh')
            cfg_cmds.append(os.path.normpath(shell.getJsCfgPath()))
            cfg_cmds.append('--target=i386-apple-darwin15.6.0')  # El Capitan 10.11.6
            cfg_cmds.append('--disable-xcode-checks')
            if shell.build_opts.buildWithAsan:
                cfg_cmds.append('--enable-address-sanitizer')
            if shell.build_opts.enableSimulatorArm32:
                # --enable-arm-simulator became --enable-simulator=arm in rev 25e99bc12482
                # but unknown flags are ignored, so we compile using both till Fx38 ESR is deprecated
                # Newer configure.in changes mean that things blow up if unknown/removed configure
                # options are entered, so specify it only if it's requested.
                if shell.build_opts.enableArmSimulatorObsolete:
                    cfg_cmds.append('--enable-arm-simulator')
                cfg_cmds.append('--enable-simulator=arm')
        # 32-bit shell on 32/64-bit x86 Linux
        elif sps.isLinux:
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
            cfg_cmds.append('sh')
            cfg_cmds.append(os.path.normpath(shell.getJsCfgPath()))
            cfg_cmds.append('--target=i686-pc-linux')
            if shell.build_opts.buildWithAsan:
                cfg_cmds.append('--enable-address-sanitizer')
            if shell.build_opts.enableSimulatorArm32:
                # --enable-arm-simulator became --enable-simulator=arm in rev 25e99bc12482
                # but unknown flags are ignored, so we compile using both till Fx38 ESR is deprecated
                # Newer configure.in changes mean that things blow up if unknown/removed configure
                # options are entered, so specify it only if it's requested.
                if shell.build_opts.enableArmSimulatorObsolete:
                    cfg_cmds.append('--enable-arm-simulator')
                cfg_cmds.append('--enable-simulator=arm')
        else:
            cfg_cmds.append('sh')
            cfg_cmds.append(os.path.normpath(shell.getJsCfgPath()))
    # 64-bit shell on Mac OS X 10.11 El Capitan and greater
    elif sps.isMac and sps.macVer() >= [10, 11] and not shell.build_opts.enable32:
        cfg_env["CC"] = "clang " + CLANG_PARAMS
        cfg_env["CXX"] = "clang++ " + CLANG_PARAMS
        if shell.build_opts.buildWithAsan:
            cfg_env["CC"] += " " + CLANG_ASAN_PARAMS
            cfg_env["CXX"] += " " + CLANG_ASAN_PARAMS
        if subprocess.check_call(["which", "brew"], stdout=subprocess.PIPE):
            cfg_env["AUTOCONF"] = "/usr/local/Cellar/autoconf213/2.13/bin/autoconf213"
        cfg_cmds.append('sh')
        cfg_cmds.append(os.path.normpath(shell.getJsCfgPath()))
        cfg_cmds.append('--target=x86_64-apple-darwin15.6.0')  # El Capitan 10.11.6
        cfg_cmds.append('--disable-xcode-checks')
        if shell.build_opts.buildWithAsan:
            cfg_cmds.append('--enable-address-sanitizer')
        if shell.build_opts.enableSimulatorArm64:
            cfg_cmds.append('--enable-simulator=arm64')

    elif sps.isWin:
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
        cfg_cmds.append('sh')
        cfg_cmds.append(os.path.normpath(shell.getJsCfgPath()))
        if shell.build_opts.enable32:
            if shell.build_opts.enableSimulatorArm32:
                # --enable-arm-simulator became --enable-simulator=arm in rev 25e99bc12482
                # but unknown flags are ignored, so we compile using both till Fx38 ESR is deprecated
                # Newer configure.in changes mean that things blow up if unknown/removed configure
                # options are entered, so specify it only if it's requested.
                if shell.build_opts.enableArmSimulatorObsolete:
                    cfg_cmds.append('--enable-arm-simulator')
                cfg_cmds.append('--enable-simulator=arm')
        else:
            cfg_cmds.append('--host=x86_64-pc-mingw32')
            cfg_cmds.append('--target=x86_64-pc-mingw32')
            if shell.build_opts.enableSimulatorArm64:
                cfg_cmds.append('--enable-simulator=arm64')
        if shell.build_opts.buildWithAsan:
            cfg_cmds.append('--enable-address-sanitizer')
    else:
        # We might still be using GCC on Linux 64-bit, so do not use clang unless Asan is specified
        if shell.build_opts.buildWithClang:
            cfg_env["CC"] = "clang " + CLANG_PARAMS
            cfg_env["CXX"] = "clang++ " + CLANG_PARAMS
        if shell.build_opts.buildWithAsan:
            cfg_env["CC"] += " " + CLANG_ASAN_PARAMS
            cfg_env["CXX"] += " " + CLANG_ASAN_PARAMS
        cfg_cmds.append('sh')
        cfg_cmds.append(os.path.normpath(shell.getJsCfgPath()))
        if shell.build_opts.buildWithAsan:
            cfg_cmds.append('--enable-address-sanitizer')

    if shell.build_opts.buildWithClang:
        if sps.isWin:
            assert "clang-cl" in cfg_env["CC"]
            assert "clang-cl" in cfg_env["CXX"]
        else:
            assert "clang" in cfg_env["CC"]
            assert "clang++" in cfg_env["CXX"]
        cfg_cmds.append('--disable-jemalloc')  # See bug 1146895

    if shell.build_opts.enableDbg:
        cfg_cmds.append('--enable-debug')
    elif shell.build_opts.disableDbg:
        cfg_cmds.append('--disable-debug')

    if shell.build_opts.enableOpt:
        cfg_cmds.append('--enable-optimize' + ('=-O1' if shell.build_opts.buildWithVg else ''))
    elif shell.build_opts.disableOpt:
        cfg_cmds.append('--disable-optimize')
    if shell.build_opts.enableProfiling:  # Now obsolete, retained for backward compatibility
        cfg_cmds.append('--enable-profiling')
    if shell.build_opts.disableProfiling:
        cfg_cmds.append('--disable-profiling')

    if shell.build_opts.enableMoreDeterministic:
        # Fuzzing tweaks for more useful output, implemented in bug 706433
        cfg_cmds.append('--enable-more-deterministic')
    if shell.build_opts.enableOomBreakpoint:  # Extra debugging help for OOM assertions
        cfg_cmds.append('--enable-oom-breakpoint')
    if shell.build_opts.enableWithoutIntlApi:  # Speeds up compilation but is non-default
        cfg_cmds.append('--without-intl-api')

    if shell.build_opts.buildWithVg:
        cfg_cmds.append('--enable-valgrind')
        cfg_cmds.append('--disable-jemalloc')

    # We add the following flags by default.
    if os.name == 'posix':
        cfg_cmds.append('--with-ccache')
    cfg_cmds.append('--enable-gczeal')
    cfg_cmds.append('--enable-debug-symbols')  # gets debug symbols on opt shells
    cfg_cmds.append('--disable-tests')

    if os.name == 'nt':
        # FIXME: Replace this with sps.shellify.  # pylint: disable=fixme
        counter = 0
        for entry in cfg_cmds:
            if os.sep in entry:
                assert sps.isWin  # MozillaBuild on Windows sometimes confuses "/" and "\".
                cfg_cmds[counter] = cfg_cmds[counter].replace(os.sep, '//')
            counter = counter + 1

    # Print whatever we added to the environment
    env_vars = []
    for env_var in set(cfg_env.keys()) - set(orig_cfg_env.keys()):
        str_to_be_appended = str(env_var + '="' + cfg_env[str(env_var)] +
                                 '"' if " " in cfg_env[str(env_var)] else env_var +
                                 "=" + cfg_env[str(env_var)])
        env_vars.append(str_to_be_appended)
    sps.vdump('Command to be run is: ' + sps.shellify(env_vars) + ' ' + sps.shellify(cfg_cmds))

    js_objdir = shell.getJsObjdir()
    assert os.path.isdir(js_objdir)

    if sps.isWin:
        changed_cfg_cmds = []
        for entry in cfg_cmds:
            # For JS, quoted from :glandium: "the way icu subconfigure is called is what changed.
            #   but really, the whole thing likes forward slashes way better"
            # See bug 1038590 comment 9.
            if '\\' in entry:
                entry = entry.replace('\\', '/')
            changed_cfg_cmds.append(entry)
        sps.captureStdout(changed_cfg_cmds, ignoreStderr=True, currWorkingDir=js_objdir, env=cfg_env)
    else:
        sps.captureStdout(cfg_cmds, ignoreStderr=True, currWorkingDir=js_objdir, env=cfg_env)

    shell.setEnvAdded(env_vars)
    shell.setEnvFull(cfg_env)
    shell.setCfgCmdExclEnv(cfg_cmds)


def compileJs(shell):  # pylint: disable=invalid-name,missing-param-doc,missing-raises-doc,missing-type-doc
    """Compile and copy a binary."""
    try:
        cmd_list = [MAKE_BINARY, '-C', shell.getJsObjdir(), '-j' + str(COMPILATION_JOBS), '-s']
        out = sps.captureStdout(cmd_list, combineStderr=True, ignoreExitCode=True,
                                currWorkingDir=shell.getJsObjdir(), env=shell.getEnvFull())[0]
    except Exception as ex:  # pylint: disable=broad-except
        # This exception message is returned from sps.captureStdout via cmd_list.
        if (sps.isLinux or sps.isMac) and \
                ('GCC running out of memory' in repr(ex) or 'Clang running out of memory' in repr(ex)):
            # FIXME: Absolute hack to retry after hitting OOM.  # pylint: disable=fixme
            print("Trying once more due to the compiler running out of memory...")
            out = sps.captureStdout(cmd_list, combineStderr=True, ignoreExitCode=True,
                                    currWorkingDir=shell.getJsObjdir(), env=shell.getEnvFull())[0]
        # A non-zero error can be returned during make, but eventually a shell still gets compiled.
        if os.path.exists(shell.getShellCompiledPath()):
            print("A shell was compiled even though there was a non-zero exit code. Continuing...")
        else:
            print("%s did not result in a js shell:" % MAKE_BINARY.decode("utf-8", errors="replace"))
            raise

    if os.path.exists(shell.getShellCompiledPath()):
        shutil.copy2(shell.getShellCompiledPath(), shell.getShellCacheFullPath())
        for run_lib in shell.getShellCompiledRunLibsPath():
            if os.path.isfile(run_lib):
                shutil.copy2(run_lib, shell.getShellCacheDir())

        version = extractVersions(shell.getJsObjdir())
        shell.setMajorVersion(version.split('.')[0])
        shell.setVersion(version)

        if sps.isLinux:
            # Restrict this to only Linux for now. At least Mac OS X needs some (possibly *.a)
            # files in the objdir or else the stacks from failing testcases will lack symbols.
            shutil.rmtree(sps.normExpUserPath(os.path.join(shell.getShellCacheDir(), 'objdir-js')))
    else:
        print(out.decode("utf-8", errors="replace"))
        raise Exception(MAKE_BINARY + " did not result in a js shell, no exception thrown.")


def createBustedFile(filename, e):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc
    """Create a .busted file with the exception message and backtrace included."""
    with open(filename, 'w') as f:
        f.write("Caught exception %r (%s)\n" % (e, e))
        f.write("Backtrace:\n")
        f.write(traceback.format_exc() + "\n")

    print("Compilation failed (%s) (details in %s)" % (e, filename))


def envDump(shell, log):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc
    """Dump environment to a .fuzzmanagerconf file."""
    # Platform and OS detection for the spec, part of which is in:
    #   https://wiki.mozilla.org/Security/CrashSignatures
    fmconf_platform = "x86" if shell.build_opts.enable32 else "x86-64"

    if sps.isLinux:
        fmconf_os = 'linux'
    elif sps.isMac:
        fmconf_os = 'macosx'
    elif sps.isWin:
        fmconf_os = 'windows'

    with open(log, "a") as f:
        f.write('# Information about shell:\n# \n')

        f.write('# Create another shell in shell-cache like this one:\n')
        f.write('# python -u -m %s -b "%s" -r %s\n# \n' % ('funfuzz.js.compile_shell',
                                                           shell.build_opts.build_options_str, shell.getHgHash()))

        f.write('# Full environment is:\n')
        f.write('# %s\n# \n' % str(shell.getEnvFull()))

        f.write('# Full configuration command with needed environment variables is:\n')
        f.write('# %s %s\n# \n' % (sps.shellify(shell.getEnvAdded()),
                                   sps.shellify(shell.getCfgCmdExclEnv())))

        # .fuzzmanagerconf details
        f.write('\n')
        f.write('[Main]\n')
        f.write('platform = %s\n' % fmconf_platform)
        f.write('product = %s\n' % shell.getRepoName())
        f.write('product_version = %s\n' % shell.getHgHash())
        f.write('os = %s\n' % fmconf_os)

        f.write('\n')
        f.write('[Metadata]\n')
        f.write('buildFlags = %s\n' % shell.build_opts.build_options_str)
        f.write('majorVersion = %s\n' % shell.getMajorVersion())
        f.write('pathPrefix = %s%s\n' % (shell.getRepoDir(),
                                         '/' if not shell.getRepoDir().endswith('/') else ''))
        f.write('version = %s\n' % shell.getVersion())


def extractVersions(objdir):  # pylint: disable=inconsistent-return-statements,invalid-name,missing-param-doc
    # pylint: disable=missing-return-doc,missing-return-type-doc,missing-type-doc
    """Extract the version from js.pc and put it into *.fuzzmanagerconf."""
    jspc_dir = sps.normExpUserPath(os.path.join(objdir, 'js', 'src'))
    jspc_name = os.path.join(jspc_dir, 'js.pc')
    # Moved to <objdir>/js/src/build/, see bug 1262241, Fx55 rev 2159959522f4
    jspc_new_dir = os.path.join(jspc_dir, 'build')
    jspc_new_name = os.path.join(jspc_new_dir, 'js.pc')

    def fixateVer(pcfile):  # pylint: disable=inconsistent-return-statements,invalid-name,missing-param-doc
        # pylint: disable=missing-return-doc,missing-return-type-doc,missing-type-doc
        """Returns the current version number (47.0a2)."""
        with io.open(pcfile, mode='r', encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith('Version: '):
                    # Sample line: 'Version: 47.0a2'
                    return line.split(': ')[1].rstrip()

    if os.path.isfile(jspc_name):
        return fixateVer(jspc_name)
    elif os.path.isfile(jspc_new_name):
        return fixateVer(jspc_new_name)


def getLockDirPath(repoDir, tboxIdentifier=''):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Return the name of the lock directory, which is in the cache directory by default."""
    lockdir_name = ['shell', os.path.basename(repoDir), 'lock']
    if tboxIdentifier:
        lockdir_name.append(tboxIdentifier)
    return os.path.join(ensureCacheDir(), '-'.join(lockdir_name))


def makeTestRev(options):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    def testRev(rev):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
        shell = CompiledShell(options.build_options, rev)
        print("Rev %s:" % rev.decode("utf-8", errors="replace"), end=" ")

        try:
            obtainShell(shell, updateToRev=rev)
        except Exception:  # pylint: disable=broad-except
            return (options.compilationFailedLabel, 'compilation failed')

        print("Testing...", end=" ")
        return options.testAndLabel(shell.getShellCacheFullPath(), rev)
    return testRev


def obtainShell(shell, updateToRev=None, updateLatestTxt=False):  # pylint: disable=invalid-name,missing-param-doc
    # pylint: disable=missing-raises-doc,missing-type-doc,too-many-branches,too-complex,too-many-statements
    """Obtain a js shell. Keep the objdir for now, especially .a files, for symbols."""
    assert os.path.isdir(getLockDirPath(shell.build_opts.repoDir))
    cached_no_shell = shell.getShellCacheFullPath() + ".busted"

    if os.path.isfile(shell.getShellCacheFullPath()):
        # Don't remove the comma at the end of this line, and thus remove the newline printed.
        # We would break JSBugMon.
        print("Found cached shell...")
        # Assuming that since the binary is present, everything else (e.g. symbols) is also present
        verifyFullWinPageHeap(shell.getShellCacheFullPath())
        return
    elif os.path.isfile(cached_no_shell):
        raise Exception("Found a cached shell that failed compilation...")
    elif os.path.isdir(shell.getShellCacheDir()):
        print("Found a cache dir without a successful/failed shell...")
        sps.rmTreeIncludingReadOnly(shell.getShellCacheDir())

    os.mkdir(shell.getShellCacheDir())
    hg_helpers.destroyPyc(shell.build_opts.repoDir)

    s3cache_obj = s3cache.S3Cache(S3_SHELL_CACHE_DIRNAME)
    use_s3cache = s3cache_obj.connect()

    if use_s3cache:
        if s3cache_obj.downloadFile(shell.getShellNameWithoutExt() + '.busted',
                                    shell.getShellCacheFullPath() + '.busted'):
            raise Exception('Found a .busted file for rev ' + shell.getHgHash())

        if s3cache_obj.downloadFile(shell.getShellNameWithoutExt() + '.tar.bz2',
                                    shell.getS3TarballWithExtFullPath()):
            print("Extracting shell...")
            with tarfile.open(shell.getS3TarballWithExtFullPath(), 'r') as f:
                f.extractall(shell.getShellCacheDir())
            # Delete tarball after downloading from S3
            os.remove(shell.getS3TarballWithExtFullPath())
            verifyFullWinPageHeap(shell.getShellCacheFullPath())
            return

    try:
        if updateToRev:
            updateRepo(shell.build_opts.repoDir, updateToRev)
        if shell.build_opts.patchFile:
            hg_helpers.patchHgRepoUsingMq(shell.build_opts.patchFile, shell.getRepoDir())

        cfgJsCompile(shell)
        verifyFullWinPageHeap(shell.getShellCacheFullPath())
    except KeyboardInterrupt:
        sps.rmTreeIncludingReadOnly(shell.getShellCacheDir())
        raise
    except Exception as ex:
        # Remove the cache dir, but recreate it with only the .busted file.
        sps.rmTreeIncludingReadOnly(shell.getShellCacheDir())
        os.mkdir(shell.getShellCacheDir())
        createBustedFile(cached_no_shell, ex)
        if use_s3cache:
            s3cache_obj.uploadFileToS3(shell.getShellCacheFullPath() + '.busted')
        raise
    finally:
        if shell.build_opts.patchFile:
            hg_helpers.hgQpopQrmAppliedPatch(shell.build_opts.patchFile, shell.getRepoDir())

    if use_s3cache:
        s3cache_obj.compressAndUploadDirTarball(shell.getShellCacheDir(), shell.getS3TarballWithExtFullPath())
        if updateLatestTxt:
            # So js-dbg-64-dm-darwin-cdcd33fd6e39 becomes js-dbg-64-dm-darwin-latest.txt with
            # js-dbg-64-dm-darwin-cdcd33fd6e39 as its contents.
            txt_info = '-'.join(shell.getS3TarballWithExt().split('-')[:-1] + ['latest']) + '.txt'
            s3cache_obj.uploadStrToS3('', txt_info, shell.getS3TarballWithExt())
        os.remove(shell.getS3TarballWithExtFullPath())


def updateRepo(repo, rev):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc
    """Update repository to the specific revision."""
    # Print *with* a trailing newline to avoid breaking other stuff
    print("Updating to rev %s in the %s repository..." % (rev.decode("utf-8", errors="replace"),
                                                          repo.decode("utf-8", errors="replace")))
    sps.captureStdout(["hg", "-R", repo, 'update', '-C', '-r', rev], ignoreStderr=True)


def verifyFullWinPageHeap(shellPath):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc
    """Turn on full page heap verification on Windows."""
    # More info: https://msdn.microsoft.com/en-us/library/windows/hardware/ff543097(v=vs.85).aspx
    # or https://blogs.msdn.microsoft.com/webdav_101/2010/06/22/detecting-heap-corruption-using-gflags-and-dumps/
    if sps.isWin:
        gflags_bin_path = os.path.join(os.getenv('PROGRAMW6432'), 'Debugging Tools for Windows (x64)', 'gflags.exe')
        if os.path.isfile(gflags_bin_path) and os.path.isfile(shellPath):
            print(subprocess.check_output([gflags_bin_path.decode("utf-8", errors="replace"),
                                           "-p", "/enable", shellPath.decode("utf-8", errors="replace"), "/full"]))


def main():
    """Execute main() function in CompiledShell class."""
    exit(CompiledShell.main())


if __name__ == '__main__':
    main()

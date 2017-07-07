#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import absolute_import

import copy
import ctypes
import multiprocessing
import os
import shutil
import subprocess
import sys
import tarfile
import traceback

from optparse import OptionParser

import buildOptions
import inspectShell

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
import hgCmds
import s3cache
import subprocesses as sps
from LockDir import LockDir

S3_SHELL_CACHE_DIRNAME = 'shell-cache'  # Used by autoBisect

if sps.isWin:
    MAKE_BINARY = 'mozmake'
    CLANG_PARAMS = ' -fallback'
    # CLANG_ASAN_PARAMS = ' -fsanitize=address -Dxmalloc=myxmalloc'
    # Note that Windows ASan builds are still a work-in-progress
    CLANG_ASAN_PARAMS = ''
else:
    MAKE_BINARY = 'make'
    CLANG_PARAMS = ' -Qunused-arguments'
    # See https://bugzilla.mozilla.org/show_bug.cgi?id=935795#c3 for some of the following flags:
    # CLANG_ASAN_PARAMS = ' -fsanitize=address -Dxmalloc=myxmalloc -mllvm -asan-stack=0'
    CLANG_ASAN_PARAMS = ' -fsanitize=address -Dxmalloc=myxmalloc'  # The flags above seem to fix a problem not on the js shell.
    SSE2_FLAGS = ' -msse2 -mfpmath=sse'  # See bug 948321
    CLANG_X86_FLAG = ' -arch i386'

if multiprocessing.cpu_count() > 2:
    COMPILATION_JOBS = ((multiprocessing.cpu_count() * 5) // 4)
elif sps.isARMv7l:
    COMPILATION_JOBS = 3  # An ARM board
else:
    COMPILATION_JOBS = 3  # Other single/dual core computers


class CompiledShell(object):
    def __init__(self, buildOpts, hgHash):
        self.shellNameWithoutExt = buildOptions.computeShellName(buildOpts, hgHash)
        self.shellNameWithExt = self.shellNameWithoutExt + ('.exe' if sps.isWin else '')
        self.hgHash = hgHash
        self.buildOptions = buildOpts

        self.jsObjdir = ''

        self.cfg = ''
        self.destDir = ''
        self.addedEnv = ''
        self.fullEnv = ''
        self.jsCfgFile = ''

        self.jsMajorVersion = ''
        self.jsVersion = ''

    def getCfgCmdExclEnv(self):
        return self.cfg

    def setCfgCmdExclEnv(self, cfg):
        self.cfg = cfg

    def setEnvAdded(self, addedEnv):
        self.addedEnv = addedEnv

    def getEnvAdded(self):
        return self.addedEnv

    def setEnvFull(self, fullEnv):
        self.fullEnv = fullEnv

    def getEnvFull(self):
        return self.fullEnv

    def getHgHash(self):
        return self.hgHash

    def getJsCfgPath(self):
        self.jsCfgFile = sps.normExpUserPath(os.path.join(self.getRepoDirJsSrc(), 'configure'))
        assert os.path.isfile(self.jsCfgFile)
        return self.jsCfgFile

    def getJsObjdir(self):
        return self.jsObjdir

    def setJsObjdir(self, oDir):
        self.jsObjdir = oDir

    def getRepoDir(self):
        return self.buildOptions.repoDir

    def getRepoDirJsSrc(self):
        return sps.normExpUserPath(os.path.join(self.getRepoDir(), 'js', 'src'))

    def getRepoName(self):
        return hgCmds.getRepoNameFromHgrc(self.buildOptions.repoDir)

    def getS3TarballWithExt(self):
        return self.getShellNameWithoutExt() + '.tar.bz2'

    def getS3TarballWithExtFullPath(self):
        return sps.normExpUserPath(os.path.join(ensureCacheDir(), self.getS3TarballWithExt()))

    def getShellCacheDir(self):
        return sps.normExpUserPath(os.path.join(ensureCacheDir(), self.getShellNameWithoutExt()))

    def getShellCacheFullPath(self):
        return sps.normExpUserPath(os.path.join(self.getShellCacheDir(), self.getShellNameWithExt()))

    def getShellCompiledPath(self):
        return sps.normExpUserPath(
            os.path.join(self.getJsObjdir(), 'dist', 'bin', 'js' + ('.exe' if sps.isWin else '')))

    def getShellCompiledRunLibsPath(self):
        lDir = self.getJsObjdir()
        libsList = [
            sps.normExpUserPath(os.path.join(lDir, 'dist', 'bin', runLib))
            for runLib in inspectShell.ALL_RUN_LIBS
        ]
        return libsList

    def getShellNameWithExt(self):
        return self.shellNameWithExt

    def getShellNameWithoutExt(self):
        return self.shellNameWithoutExt

    # Version numbers
    def getMajorVersion(self):
        return self.jsMajorVersion

    def setMajorVersion(self, jsMajorVersion):
        self.jsMajorVersion = jsMajorVersion

    def getVersion(self):
        return self.jsVersion

    def setVersion(self, jsVersion):
        self.jsVersion = jsVersion


def ensureCacheDir():
    """Return a cache directory for compiled shells to live in, and create one if needed."""
    cacheDir = os.path.join(sps.normExpUserPath('~'), 'shell-cache')
    ensureDir(cacheDir)

    # Expand long Windows paths (overcome legacy MS-DOS 8.3 stuff)
    # This has to occur after the shell-cache directory is created
    if sps.isWin:  # adapted from http://stackoverflow.com/a/3931799
        winTmpDir = unicode(cacheDir)
        GetLongPathName = ctypes.windll.kernel32.GetLongPathNameW
        unicodeBuffer = ctypes.create_unicode_buffer(GetLongPathName(winTmpDir, 0, 0))
        GetLongPathName(winTmpDir, unicodeBuffer, len(unicodeBuffer))
        cacheDir = sps.normExpUserPath(str(unicodeBuffer.value))  # convert back to a str

    return cacheDir


def ensureDir(directory):
    """Create a directory, if it does not already exist."""
    if not os.path.exists(directory):
        os.mkdir(directory)
    assert os.path.isdir(directory)


def autoconfRun(cwDir):
    """Run autoconf binaries corresponding to the platform."""
    if sps.isMac:
        autoconf213MacBin = '/usr/local/Cellar/autoconf213/2.13/bin/autoconf213' \
                            if sps.isProgramInstalled('brew') else 'autoconf213'
        # Total hack to support new and old Homebrew configs, we can probably just call autoconf213
        if not os.path.isfile(sps.normExpUserPath(autoconf213MacBin)):
            autoconf213MacBin = 'autoconf213'
        subprocess.check_call([autoconf213MacBin], cwd=cwDir)
    elif sps.isLinux:
        # FIXME: We should use a method that is similar to the client.mk one, as per
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


def cfgJsCompile(shell):
    """Configures, compiles and copies a js shell according to required parameters."""
    print "Compiling..."  # Print *with* a trailing newline to avoid breaking other stuff
    os.mkdir(sps.normExpUserPath(os.path.join(shell.getShellCacheDir(), 'objdir-js')))
    shell.setJsObjdir(sps.normExpUserPath(os.path.join(shell.getShellCacheDir(), 'objdir-js')))

    autoconfRun(shell.getRepoDirJsSrc())
    configureTryCount = 0
    while True:
        try:
            cfgBin(shell)
            break
        except Exception as e:
            configureTryCount += 1
            if configureTryCount > 3:
                print 'Configuration of the js binary failed 3 times.'
                raise
            # This exception message is returned from sps.captureStdout via cfgBin.
            # No idea why this is sps.isLinux as well..
            if sps.isLinux or (sps.isWin and 'Windows conftest.exe configuration permission' in repr(e)):
                print 'Trying once more...'
                continue
    compileJs(shell)
    inspectShell.verifyBinary(shell)

    compileLog = sps.normExpUserPath(os.path.join(shell.getShellCacheDir(),
                                                  shell.getShellNameWithoutExt() + '.fuzzmanagerconf'))
    if not os.path.isfile(compileLog):
        envDump(shell, compileLog)


def cfgBin(shell):
    """Configure a binary according to required parameters."""
    cfgCmdList = []
    cfgEnvDt = copy.deepcopy(os.environ)
    origCfgEnvDt = copy.deepcopy(os.environ)
    cfgEnvDt['AR'] = 'ar'
    if sps.isARMv7l:
        # 32-bit shell on ARM boards, e.g. odroid boards.
        # This is tested on Ubuntu 14.04 with necessary armel libraries (force)-installed.
        assert shell.buildOptions.enable32, 'arm7vl boards are only 32-bit, armv8 boards will be 64-bit.'
        if not shell.buildOptions.enableHardFp:
            cfgEnvDt['CC'] = 'gcc-4.7 -mfloat-abi=softfp -B/usr/lib/gcc/arm-linux-gnueabi/4.7'
            cfgEnvDt['CXX'] = 'g++-4.7 -mfloat-abi=softfp -B/usr/lib/gcc/arm-linux-gnueabi/4.7'
        cfgCmdList.append('sh')
        cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
        # From mjrosenb: things might go wrong if these three lines are not present for
        # compiling ARM on a 64-bit host machine. Not needed if compiling on the board itself.
        # cfgCmdList.append('--target=arm-linux-gnueabi')
        # cfgCmdList.append('--with-arch=armv7-a')
        # cfgCmdList.append('--with-thumb')
        if not shell.buildOptions.enableHardFp:
            cfgCmdList.append('--target=arm-linux-gnueabi')
    elif shell.buildOptions.enable32 and os.name == 'posix':
        # 32-bit shell on Mac OS X 10.10 Yosemite and greater
        if sps.isMac:
            assert sps.macVer() >= [10, 10]  # We no longer support 10.9 Mavericks and prior.
            # Uses system clang
            cfgEnvDt['CC'] = cfgEnvDt['HOST_CC'] = 'clang' + CLANG_PARAMS + SSE2_FLAGS
            cfgEnvDt['CXX'] = cfgEnvDt['HOST_CXX'] = 'clang++' + CLANG_PARAMS + SSE2_FLAGS
            if shell.buildOptions.buildWithAsan:
                cfgEnvDt['CC'] += CLANG_ASAN_PARAMS
                cfgEnvDt['CXX'] += CLANG_ASAN_PARAMS
            cfgEnvDt['CC'] = cfgEnvDt['CC'] + CLANG_X86_FLAG  # only needed for CC, not HOST_CC
            cfgEnvDt['CXX'] = cfgEnvDt['CXX'] + CLANG_X86_FLAG  # only needed for CXX, not HOST_CXX
            cfgEnvDt['RANLIB'] = 'ranlib'
            cfgEnvDt['AS'] = '$CC'
            cfgEnvDt['LD'] = 'ld'
            cfgEnvDt['STRIP'] = 'strip -x -S'
            cfgEnvDt['CROSS_COMPILE'] = '1'
            if sps.isProgramInstalled('brew'):
                cfgEnvDt['AUTOCONF'] = '/usr/local/Cellar/autoconf213/2.13/bin/autoconf213'
                # Hacked up for new and old Homebrew configs, we can probably just call autoconf213
                if not os.path.isfile(sps.normExpUserPath(cfgEnvDt['AUTOCONF'])):
                    cfgEnvDt['AUTOCONF'] = 'autoconf213'
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
            cfgCmdList.append('--target=i386-apple-darwin14.5.0')  # Yosemite 10.10.5
            if shell.buildOptions.buildWithAsan:
                cfgCmdList.append('--enable-address-sanitizer')
            if shell.buildOptions.enableSimulatorArm32:
                # --enable-arm-simulator became --enable-simulator=arm in rev 25e99bc12482
                # but unknown flags are ignored, so we compile using both till Fx38 ESR is deprecated
                # Newer configure.in changes mean that things blow up if unknown/removed configure
                # options are entered, so specify it only if it's requested.
                if shell.buildOptions.enableArmSimulatorObsolete:
                    cfgCmdList.append('--enable-arm-simulator')
                cfgCmdList.append('--enable-simulator=arm')
        # 32-bit shell on 32/64-bit x86 Linux
        elif sps.isLinux and not sps.isARMv7l:
            cfgEnvDt['PKG_CONFIG_LIBDIR'] = '/usr/lib/pkgconfig'
            if shell.buildOptions.buildWithClang:
                cfgEnvDt['CC'] = cfgEnvDt['HOST_CC'] = 'clang' + CLANG_PARAMS + SSE2_FLAGS + CLANG_X86_FLAG
                cfgEnvDt['CXX'] = cfgEnvDt['HOST_CXX'] = 'clang++' + CLANG_PARAMS + SSE2_FLAGS + CLANG_X86_FLAG
            else:
                # apt-get `lib32z1 gcc-multilib g++-multilib` first, if on 64-bit Linux.
                cfgEnvDt['CC'] = 'gcc -m32' + SSE2_FLAGS
                cfgEnvDt['CXX'] = 'g++ -m32' + SSE2_FLAGS
            if shell.buildOptions.buildWithAsan:
                cfgEnvDt['CC'] += CLANG_ASAN_PARAMS
                cfgEnvDt['CXX'] += CLANG_ASAN_PARAMS
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
            cfgCmdList.append('--target=i686-pc-linux')
            if shell.buildOptions.buildWithAsan:
                cfgCmdList.append('--enable-address-sanitizer')
            if shell.buildOptions.enableSimulatorArm32:
                # --enable-arm-simulator became --enable-simulator=arm in rev 25e99bc12482
                # but unknown flags are ignored, so we compile using both till Fx38 ESR is deprecated
                # Newer configure.in changes mean that things blow up if unknown/removed configure
                # options are entered, so specify it only if it's requested.
                if shell.buildOptions.enableArmSimulatorObsolete:
                    cfgCmdList.append('--enable-arm-simulator')
                cfgCmdList.append('--enable-simulator=arm')
        else:
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
    # 64-bit shell on Mac OS X 10.10 Yosemite and greater
    elif sps.isMac and sps.macVer() >= [10, 10] and not shell.buildOptions.enable32:
        cfgEnvDt['CC'] = 'clang' + CLANG_PARAMS
        cfgEnvDt['CXX'] = 'clang++' + CLANG_PARAMS
        if shell.buildOptions.buildWithAsan:
            cfgEnvDt['CC'] += CLANG_ASAN_PARAMS
            cfgEnvDt['CXX'] += CLANG_ASAN_PARAMS
        if sps.isProgramInstalled('brew'):
            cfgEnvDt['AUTOCONF'] = '/usr/local/Cellar/autoconf213/2.13/bin/autoconf213'
        cfgCmdList.append('sh')
        cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
        cfgCmdList.append('--target=x86_64-apple-darwin14.5.0')  # Yosemite 10.10.5
        if shell.buildOptions.buildWithAsan:
            cfgCmdList.append('--enable-address-sanitizer')
        if shell.buildOptions.enableSimulatorArm64:
            cfgCmdList.append('--enable-simulator=arm64')

    elif sps.isWin:
        cfgEnvDt['MAKE'] = 'mozmake'  # Workaround for bug 948534
        if shell.buildOptions.buildWithClang:
            cfgEnvDt['CC'] = 'clang-cl.exe' + CLANG_PARAMS
            cfgEnvDt['CXX'] = 'clang-cl.exe' + CLANG_PARAMS
        if shell.buildOptions.buildWithAsan:
            cfgEnvDt['CFLAGS'] = CLANG_ASAN_PARAMS
            cfgEnvDt['CXXFLAGS'] = CLANG_ASAN_PARAMS
            cfgEnvDt['LDFLAGS'] = "clang_rt.asan_dynamic-x86_64.lib clang_rt.asan_dynamic_runtime_thunk-x86_64.lib clang_rt.asan_dynamic-x86_64.dll"
            cfgEnvDt['HOST_CFLAGS'] = ' '
            cfgEnvDt['HOST_CXXFLAGS'] = ' '
            cfgEnvDt['HOST_LDFLAGS'] = ' '
            cfgEnvDt['LIB'] += "C:\\Program Files\\LLVM\\lib\\clang\\4.0.0\\lib\\windows"
        cfgCmdList.append('sh')
        cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
        if shell.buildOptions.enable32:
            if shell.buildOptions.enableSimulatorArm32:
                # --enable-arm-simulator became --enable-simulator=arm in rev 25e99bc12482
                # but unknown flags are ignored, so we compile using both till Fx38 ESR is deprecated
                # Newer configure.in changes mean that things blow up if unknown/removed configure
                # options are entered, so specify it only if it's requested.
                if shell.buildOptions.enableArmSimulatorObsolete:
                    cfgCmdList.append('--enable-arm-simulator')
                cfgCmdList.append('--enable-simulator=arm')
        else:
            cfgCmdList.append('--host=x86_64-pc-mingw32')
            cfgCmdList.append('--target=x86_64-pc-mingw32')
            if shell.buildOptions.enableSimulatorArm64:
                cfgCmdList.append('--enable-simulator=arm64')
        if shell.buildOptions.buildWithAsan:
            cfgCmdList.append('--enable-address-sanitizer')
    else:
        # We might still be using GCC on Linux 64-bit, so do not use clang unless Asan is specified
        if shell.buildOptions.buildWithClang:
            cfgEnvDt['CC'] = 'clang' + CLANG_PARAMS
            cfgEnvDt['CXX'] = 'clang++' + CLANG_PARAMS
        if shell.buildOptions.buildWithAsan:
            cfgEnvDt['CC'] += CLANG_ASAN_PARAMS
            cfgEnvDt['CXX'] += CLANG_ASAN_PARAMS
        cfgCmdList.append('sh')
        cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
        if shell.buildOptions.buildWithAsan:
            cfgCmdList.append('--enable-address-sanitizer')

    if shell.buildOptions.buildWithClang:
        if sps.isWin:
            assert 'clang-cl' in cfgEnvDt['CC']
            assert 'clang-cl' in cfgEnvDt['CXX']
        else:
            assert 'clang' in cfgEnvDt['CC']
            assert 'clang++' in cfgEnvDt['CXX']
        cfgCmdList.append('--disable-jemalloc')  # See bug 1146895

    if shell.buildOptions.enableDbg:
        cfgCmdList.append('--enable-debug')
    elif shell.buildOptions.disableDbg:
        cfgCmdList.append('--disable-debug')

    if shell.buildOptions.enableOpt:
        cfgCmdList.append('--enable-optimize' + ('=-O1' if shell.buildOptions.buildWithVg else ''))
    elif shell.buildOptions.disableOpt:
        cfgCmdList.append('--disable-optimize')
    if shell.buildOptions.enableProfiling:  # Now obsolete, retained for backward compatibility
        cfgCmdList.append('--enable-profiling')
    if shell.buildOptions.disableProfiling:
        cfgCmdList.append('--disable-profiling')

    if shell.buildOptions.enableMoreDeterministic:
        # Fuzzing tweaks for more useful output, implemented in bug 706433
        cfgCmdList.append('--enable-more-deterministic')
    if shell.buildOptions.enableOomBreakpoint:  # Extra debugging help for OOM assertions
        cfgCmdList.append('--enable-oom-breakpoint')
    if shell.buildOptions.enableWithoutIntlApi:  # Speeds up compilation but is non-default
        cfgCmdList.append('--without-intl-api')

    if shell.buildOptions.buildWithVg:
        cfgCmdList.append('--enable-valgrind')
        cfgCmdList.append('--disable-jemalloc')

    # We add the following flags by default.
    if os.name == 'posix':
        cfgCmdList.append('--with-ccache')
    cfgCmdList.append('--enable-gczeal')
    cfgCmdList.append('--enable-debug-symbols')  # gets debug symbols on opt shells
    cfgCmdList.append('--disable-tests')

    if os.name == 'nt':
        # FIXME: Replace this with sps.shellify.
        counter = 0
        for entry in cfgCmdList:
            if os.sep in entry:
                assert sps.isWin  # MozillaBuild on Windows sometimes confuses "/" and "\".
                cfgCmdList[counter] = cfgCmdList[counter].replace(os.sep, '//')
            counter = counter + 1

    # Print whatever we added to the environment
    envVarList = []
    for envVar in set(cfgEnvDt.keys()) - set(origCfgEnvDt.keys()):
        strToBeAppended = envVar + '="' + cfgEnvDt[envVar] + '"' \
            if ' ' in cfgEnvDt[envVar] else envVar + '=' + cfgEnvDt[envVar]
        envVarList.append(strToBeAppended)
    sps.vdump('Command to be run is: ' + sps.shellify(envVarList) + ' ' + sps.shellify(cfgCmdList))

    wDir = shell.getJsObjdir()
    assert os.path.isdir(wDir)

    if sps.isWin:
        changedCfgCmdList = []
        for entry in cfgCmdList:
            # For JS, quoted from :glandium: "the way icu subconfigure is called is what changed.
            #   but really, the whole thing likes forward slashes way better"
            # See bug 1038590 comment 9.
            if '\\' in entry:
                entry = entry.replace('\\', '/')
            changedCfgCmdList.append(entry)
        sps.captureStdout(changedCfgCmdList, ignoreStderr=True, currWorkingDir=wDir, env=cfgEnvDt)
    else:
        sps.captureStdout(cfgCmdList, ignoreStderr=True, currWorkingDir=wDir, env=cfgEnvDt)

    shell.setEnvAdded(envVarList)
    shell.setEnvFull(cfgEnvDt)
    shell.setCfgCmdExclEnv(cfgCmdList)


def compileJs(shell):
    """Compile and copy a binary."""
    try:
        cmdList = [MAKE_BINARY, '-C', shell.getJsObjdir(), '-j' + str(COMPILATION_JOBS), '-s']
        out = sps.captureStdout(cmdList, combineStderr=True, ignoreExitCode=True,
                                currWorkingDir=shell.getJsObjdir(), env=shell.getEnvFull())[0]
    except Exception as e:
        # This exception message is returned from sps.captureStdout via cmdList.
        if (sps.isLinux or sps.isMac) and \
                ('GCC running out of memory' in repr(e) or 'Clang running out of memory' in repr(e)):
            # FIXME: Absolute hack to retry after hitting OOM.
            print 'Trying once more due to the compiler running out of memory...'
            out = sps.captureStdout(cmdList, combineStderr=True, ignoreExitCode=True,
                                    currWorkingDir=shell.getJsObjdir(), env=shell.getEnvFull())[0]
        # A non-zero error can be returned during make, but eventually a shell still gets compiled.
        if os.path.exists(shell.getShellCompiledPath()):
            print 'A shell was compiled even though there was a non-zero exit code. Continuing...'
        else:
            print MAKE_BINARY + " did not result in a js shell:"
            raise

    if os.path.exists(shell.getShellCompiledPath()):
        shutil.copy2(shell.getShellCompiledPath(), shell.getShellCacheFullPath())
        for runLib in shell.getShellCompiledRunLibsPath():
            if os.path.isfile(runLib):
                shutil.copy2(runLib, shell.getShellCacheDir())

        version = extractVersions(shell.getJsObjdir())
        shell.setMajorVersion(version.split('.')[0])
        shell.setVersion(version)

        if sps.isLinux:
            # Restrict this to only Linux for now. At least Mac OS X needs some (possibly *.a)
            # files in the objdir or else the stacks from failing testcases will lack symbols.
            shutil.rmtree(sps.normExpUserPath(os.path.join(shell.getShellCacheDir(), 'objdir-js')))
    else:
        print out
        raise Exception(MAKE_BINARY + " did not result in a js shell, no exception thrown.")


def createBustedFile(filename, e):
    """Create a .busted file with the exception message and backtrace included."""
    with open(filename, 'wb') as f:
        f.write("Caught exception %s (%s)\n" % (repr(e), str(e)))
        f.write("Backtrace:\n")
        f.write(traceback.format_exc() + "\n")
    print 'Compilation failed (' + str(e) + ') (details in ' + filename + ')'


def envDump(shell, log):
    """Dump environment to a .fuzzmanagerconf file."""
    # Platform and OS detection for the spec, part of which is in:
    #   https://wiki.mozilla.org/Security/CrashSignatures
    if sps.isARMv7l:
        fmconfPlatform = 'ARM'
    elif sps.isARMv7l and not shell.buildOptions.enable32:
        print 'ARM64 is not supported in .fuzzmanagerconf yet.'
        fmconfPlatform = 'ARM64'
    elif shell.buildOptions.enable32:
        fmconfPlatform = 'x86'
    else:
        fmconfPlatform = 'x86-64'

    if sps.isLinux:
        fmconfOS = 'linux'
    elif sps.isMac:
        fmconfOS = 'macosx'
    elif sps.isWin:
        fmconfOS = 'windows'

    with open(log, 'ab') as f:
        f.write('# Information about shell:\n# \n')

        f.write('# Create another shell in shell-cache like this one:\n')
        f.write('# python -u %s -b "%s" -r %s\n# \n' % ('~/funfuzz/js/compileShell.py',
                                                        shell.buildOptions.buildOptionsStr, shell.getHgHash()))

        f.write('# Full environment is:\n')
        f.write('# %s\n# \n' % str(shell.getEnvFull()))

        f.write('# Full configuration command with needed environment variables is:\n')
        f.write('# %s %s\n# \n' % (sps.shellify(shell.getEnvAdded()),
                                   sps.shellify(shell.getCfgCmdExclEnv())))

        # .fuzzmanagerconf details
        f.write('\n')
        f.write('[Main]\n')
        f.write('platform = %s\n' % fmconfPlatform)
        f.write('product = %s\n' % shell.getRepoName())
        f.write('product_version = %s\n' % shell.getHgHash())
        f.write('os = %s\n' % fmconfOS)

        f.write('\n')
        f.write('[Metadata]\n')
        f.write('buildFlags = %s\n' % shell.buildOptions.buildOptionsStr)
        f.write('majorVersion = %s\n' % shell.getMajorVersion())
        f.write('pathPrefix = %s%s\n' % (shell.getRepoDir(),
                                         '/' if not shell.getRepoDir().endswith('/') else ''))
        f.write('version = %s\n' % shell.getVersion())


def extractVersions(objdir):
    """Extract the version from js.pc and put it into *.fuzzmanagerconf."""
    jspcDir = sps.normExpUserPath(os.path.join(objdir, 'js', 'src'))
    jspcFilename = os.path.join(jspcDir, 'js.pc')
    # Moved to <objdir>/js/src/build/, see bug 1262241, Fx55 rev 2159959522f4
    jspcNewDir = os.path.join(jspcDir, 'build')
    jspcNewFilename = os.path.join(jspcNewDir, 'js.pc')

    def fixateVer(pcfile):
        """Returns the current version number (47.0a2)."""
        with open(pcfile, 'rb') as f:
            for line in f:
                if line.startswith('Version: '):
                    # Sample line: 'Version: 47.0a2'
                    return line.split(': ')[1].rstrip()

    if os.path.isfile(jspcFilename):
        return fixateVer(jspcFilename)
    elif os.path.isfile(jspcNewFilename):
        return fixateVer(jspcNewFilename)


def getLockDirPath(repoDir, tboxIdentifier=''):
    """Return the name of the lock directory, which is in the cache directory by default."""
    lockDirNameList = ['shell', os.path.basename(repoDir), 'lock']
    if tboxIdentifier:
        lockDirNameList.append(tboxIdentifier)
    return os.path.join(ensureCacheDir(), '-'.join(lockDirNameList))


def makeTestRev(options):
    def testRev(rev):
        shell = CompiledShell(options.buildOptions, rev)
        print "Rev " + rev + ":",

        try:
            obtainShell(shell, updateToRev=rev)
        except Exception:
            return (options.compilationFailedLabel, 'compilation failed')

        print "Testing...",
        return options.testAndLabel(shell.getShellCacheFullPath(), rev)
    return testRev


def obtainShell(shell, updateToRev=None, updateLatestTxt=False):
    """Obtain a js shell. Keep the objdir for now, especially .a files, for symbols."""
    assert os.path.isdir(getLockDirPath(shell.buildOptions.repoDir))
    cachedNoShell = shell.getShellCacheFullPath() + ".busted"

    if os.path.isfile(shell.getShellCacheFullPath()):
        # Don't remove the comma at the end of this line, and thus remove the newline printed.
        # We would break JSBugMon.
        print 'Found cached shell...'
        # Assuming that since the binary is present, everything else (e.g. symbols) is also present
        verifyFullWinPageHeap(shell.getShellCacheFullPath())
        return
    elif os.path.isfile(cachedNoShell):
        raise Exception("Found a cached shell that failed compilation...")
    elif os.path.isdir(shell.getShellCacheDir()):
        print 'Found a cache dir without a successful/failed shell...'
        sps.rmTreeIncludingReadOnly(shell.getShellCacheDir())

    os.mkdir(shell.getShellCacheDir())
    hgCmds.destroyPyc(shell.buildOptions.repoDir)

    s3CacheObj = s3cache.S3Cache(S3_SHELL_CACHE_DIRNAME)
    useS3Cache = s3CacheObj.connect()

    if useS3Cache:
        if s3CacheObj.downloadFile(shell.getShellNameWithoutExt() + '.busted',
                                   shell.getShellCacheFullPath() + '.busted'):
            raise Exception('Found a .busted file for rev ' + shell.getHgHash())

        if s3CacheObj.downloadFile(shell.getShellNameWithoutExt() + '.tar.bz2',
                                   shell.getS3TarballWithExtFullPath()):
            print 'Extracting shell...'
            with tarfile.open(shell.getS3TarballWithExtFullPath(), 'r') as z:
                z.extractall(shell.getShellCacheDir())
            # Delete tarball after downloading from S3
            os.remove(shell.getS3TarballWithExtFullPath())
            verifyFullWinPageHeap(shell.getShellCacheFullPath())
            return

    try:
        if updateToRev:
            updateRepo(shell.buildOptions.repoDir, updateToRev)
        if shell.buildOptions.patchFile:
            hgCmds.patchHgRepoUsingMq(shell.buildOptions.patchFile, shell.getRepoDir())

        cfgJsCompile(shell)
        verifyFullWinPageHeap(shell.getShellCacheFullPath())
    except KeyboardInterrupt:
        sps.rmTreeIncludingReadOnly(shell.getShellCacheDir())
        raise
    except Exception as e:
        # Remove the cache dir, but recreate it with only the .busted file.
        sps.rmTreeIncludingReadOnly(shell.getShellCacheDir())
        os.mkdir(shell.getShellCacheDir())
        createBustedFile(cachedNoShell, e)
        if useS3Cache:
            s3CacheObj.uploadFileToS3(shell.getShellCacheFullPath() + '.busted')
        raise
    finally:
        if shell.buildOptions.patchFile:
            hgCmds.hgQpopQrmAppliedPatch(shell.buildOptions.patchFile, shell.getRepoDir())

    if useS3Cache:
        s3CacheObj.compressAndUploadDirTarball(shell.getShellCacheDir(), shell.getS3TarballWithExtFullPath())
        if updateLatestTxt:
            # So js-dbg-64-dm-darwin-cdcd33fd6e39 becomes js-dbg-64-dm-darwin-latest.txt with
            # js-dbg-64-dm-darwin-cdcd33fd6e39 as its contents.
            txtInfo = '-'.join(shell.getS3TarballWithExt().split('-')[:-1] + ['latest']) + '.txt'
            s3CacheObj.uploadStrToS3('', txtInfo, shell.getS3TarballWithExt())
        os.remove(shell.getS3TarballWithExtFullPath())


def updateRepo(repo, rev):
    """Update repository to the specific revision."""
    # Print *with* a trailing newline to avoid breaking other stuff
    print "Updating to rev %s in the %s repository..." % (rev, repo)
    sps.captureStdout(["hg", "-R", repo, 'update', '-C', '-r', rev], ignoreStderr=True)


def verifyFullWinPageHeap(shellPath):
    """Turn on full page heap verification on Windows."""
    # More info: https://msdn.microsoft.com/en-us/library/windows/hardware/ff543097(v=vs.85).aspx
    # or https://blogs.msdn.microsoft.com/webdav_101/2010/06/22/detecting-heap-corruption-using-gflags-and-dumps/
    if sps.isWin:
        gflagsBin = os.path.join(os.getenv('PROGRAMW6432'), 'Debugging Tools for Windows (x64)', 'gflags.exe')
        if os.path.isfile(gflagsBin) and os.path.isfile(shellPath):
            print subprocess.check_output([gflagsBin, '-p', '/enable', shellPath, '/full'])


def main():
    """Build a shell and place it in the autoBisect cache."""
    usage = 'Usage: %prog [options]'
    parser = OptionParser(usage)
    parser.disable_interspersed_args()

    parser.set_defaults(
        buildOptions="",
    )

    # Specify how the shell will be built.
    # See buildOptions.py for details.
    parser.add_option('-b', '--build',
                      dest='buildOptions',
                      help='Specify build options, e.g. -b "--disable-debug --enable-optimize" ' +
                      '(python buildOptions.py --help)')

    parser.add_option('-r', '--rev',
                      dest='revision',
                      help='Specify revision to build')

    options = parser.parse_args()[0]
    options.buildOptions = buildOptions.parseShellOptions(options.buildOptions)

    with LockDir(getLockDirPath(options.buildOptions.repoDir)):
        if options.revision:
            shell = CompiledShell(options.buildOptions, options.revision)
        else:
            localOrigHgHash = hgCmds.getRepoHashAndId(options.buildOptions.repoDir)[0]
            shell = CompiledShell(options.buildOptions, localOrigHgHash)

        obtainShell(shell, updateToRev=options.revision)
        print shell.getShellCacheFullPath()


if __name__ == '__main__':
    main()

#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import with_statement

import os
import platform
import shutil
import subprocess
import sys

from copy import deepcopy
from tempfile import mkdtemp
from traceback import format_exc
from optparse import OptionParser

import buildOptions
from inspectShell import verifyBinary

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
from countCpus import cpuCount
from hgCmds import getRepoNameFromHgrc, getRepoHashAndId, getMcRepoDir, destroyPyc
from subprocesses import captureStdout, isLinux, isMac, isVM, isWin, macVer, normExpUserPath, vdump

CLANG_PARAMS = ' -Qunused-arguments'
# Replace cpuCount() with multiprocessing's cpu_count() once Python 2.6 is in all build slaves.
COMPILATION_JOBS = ((cpuCount() * 5) // 4) if cpuCount() > 2 else 3

LIBNSPR_NAME = 'libnspr4.' + ('lib' if os.name == 'nt' else 'a')
LIBPLDS_NAME = 'libplds4.' + ('lib' if os.name == 'nt' else 'a')
LIBPLC_NAME = 'libplc4.' + ('lib' if os.name == 'nt' else 'a')


class CompiledShell(object):
    def __init__(self, buildOpts, hgHash, baseTmpDir):
        self.shellName = buildOptions.computeShellName(buildOpts, hgHash) + ('.exe' if isWin else '')
        self.hgHash = hgHash
        self.buildOptions = buildOpts
        self.baseTmpDir = baseTmpDir
        assert os.path.isdir(self.baseTmpDir)
    def getBaseTempDir(self):
        return self.baseTmpDir
    def setCfgCmdExclEnv(self, cfg):
        self.cfg = cfg
    def getCfgCmdExclEnv(self):
        return self.cfg
    def getJsCfgPath(self):
        self.jsCfgFile = normExpUserPath(os.path.join(self.cPathJsSrc, 'configure'))
        assert os.path.isfile(self.jsCfgFile)
        return self.jsCfgFile
    def getNsprCfgPath(self):
        self.nsprCfgFile = normExpUserPath(os.path.join(self.cPathNsprSrc, 'configure'))
        assert os.path.isfile(self.nsprCfgFile)
        return self.nsprCfgFile
    def getCompilePath(self):
        return normExpUserPath(os.path.join(self.baseTmpDir, 'compilePath'))
    def getCompilePathJsSrc(self):
        self.cPathJsSrc = normExpUserPath(os.path.join(self.baseTmpDir, 'compilePath', 'js', 'src'))
        return self.cPathJsSrc
    def getCompilePathNsprSrc(self):
        self.cPathNsprSrc = normExpUserPath(os.path.join(self.baseTmpDir, 'compilePath', 'nsprpub'))
        return self.cPathNsprSrc
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
    def getJsObjdir(self):
        return normExpUserPath(os.path.join(self.cPathJsSrc, self.buildOptions.compileType + '-objdir'))
    def getNsprObjdir(self):
        return normExpUserPath(os.path.join(self.cPathNsprSrc, self.buildOptions.compileType + '-objdir'))
    def getRepoDir(self):
        return self.buildOptions.repoDir
    def getRepoName(self):
        return getRepoNameFromHgrc(self.buildOptions.repoDir)
    def getShellCachePath(self):
        return normExpUserPath(os.path.join(ensureCacheDir(), self.shellName))
    def getShellCompiledPath(self):
        return normExpUserPath(os.path.join(self.getJsObjdir(), 'js' + ('.exe' if isWin else '')))
    def getShellBaseTempDirWithName(self):
        return normExpUserPath(os.path.join(self.baseTmpDir, self.shellName))


def ensureCacheDir():
    '''Returns a cache directory for compiled shells to live in, creating one if needed'''

    if isVM() == ('Windows', True):
        # FIXME: Add an assertion that isVM() is a WinXP VM, and not Vista/Win7/Win8.
        # Set to root directory of Windows VM since we only test WinXP in a VM.
        # This might fail on a Vista or Win7 VM due to lack of permissions.
        # It would be good to get this machine-specific hack out of the shared file, eventually.
        cacheDirBase = os.path.join('c:', os.sep)
    # This particular machine has insufficient disk space on the main drive.
    elif isLinux and os.path.exists(os.sep + 'hddbackup'):
        cacheDirBase = os.path.join(os.sep + 'hddbackup')
    else:
        cacheDirBase = normExpUserPath(os.path.join('~', 'Desktop'))
        # If ~/Desktop is not present, create it. ~/Desktop might not be present with
        # CLI/server versions of Linux.
        ensureDir(cacheDirBase)
    cacheDir = os.path.join(cacheDirBase, 'autobisect-cache')
    ensureDir(cacheDir)
    return cacheDir

def ensureDir(dir):
    '''Creates a directory, if it does not already exist'''
    if not os.path.exists(dir):
        os.mkdir(dir)
    assert os.path.isdir(dir)

def autoconfRun(cwd):
    '''Run autoconf binaries corresponding to the platform.'''
    if isMac:
        subprocess.check_call(['autoconf213'], cwd=cwd)
    elif isLinux:
        subprocess.check_call(['autoconf2.13'], cwd=cwd)
    elif isWin:
        subprocess.check_call(['sh', 'autoconf-2.13'], cwd=cwd)

def cfgAsanParams(currEnv, options):
    '''Configures parameters that Asan needs.'''
    # https://developer.mozilla.org/en-US/docs/Building_Firefox_with_Address_Sanitizer#Manual_Build
    vdump('Assumed LLVM SVN version is: 163716')

    llvmRoot = normExpUserPath(options.llvmRootSrcDir)
    # FIXME: It would be friendlier to show instructions (or even offer to set up LLVM for the user,
    # with the right LLVM revision and build options). See MDN article on Firefox and Asan above.
    assert os.path.isdir(llvmRoot)
    currEnv['LLVM_ROOT'] = llvmRoot

    ccClang = os.path.join(llvmRoot, 'build', 'Release+Asserts', 'bin', 'clang')
    assert os.path.isfile(ccClang)
    currEnv['CC'] = ccClang + ' -faddress-sanitizer -Dxmalloc=myxmalloc'

    cxxClang = os.path.join(llvmRoot, 'build', 'Release+Asserts', 'bin', 'clang++')
    assert os.path.isfile(cxxClang)
    currEnv['CXX'] = cxxClang + ' -faddress-sanitizer -Dxmalloc=myxmalloc'

    return currEnv

def cfgJsCompileCopy(shell, options):
    '''Configures, compiles and copies a js shell according to required parameters.'''
    if options.isThreadsafe:
        compileNspr(shell, options)
    autoconfRun(shell.getCompilePathJsSrc())
    try:
        os.mkdir(shell.getJsObjdir())
    except OSError:
        raise Exception('Unable to create js objdir.')
    try:
        cfgBin(shell, options, 'js')
    except Exception, e:
        # This exception message is returned from captureStdout via cfgBin.
        if isLinux or (isWin and 'Windows conftest.exe configuration permission' in repr(e)):
            print 'Trying once more...'
            cfgBin(shell, options, 'js')
        else:
            print 'Configuration of the js binary failed.'
            raise
    compileJsCopy(shell, options)

def cfgBin(shell, options, binToBeCompiled):
    '''This function configures a binary according to required parameters.'''
    cfgCmdList = []
    cfgEnvDt = deepcopy(os.environ)
    origCfgEnvDt = deepcopy(os.environ)
    cfgEnvDt['MOZILLA_CENTRAL_PATH'] = shell.getCompilePath()  # Required by m-c 119049:d2cce982a7c8
    # For tegra Ubuntu, no special commands needed, but do install Linux prerequisites,
    # do not worry if build-dep does not work, also be sure to apt-get zip as well.
    if options.arch == '32' and os.name == 'posix' and os.uname()[1] != 'tegra-ubuntu':
        # 32-bit shell on Mac OS X 10.7 Lion and greater
        if isMac:
            assert macVer() >= [10, 7]  # We no longer support Snow Leopard 10.6 and prior.
            cfgEnvDt['CC'] = cfgEnvDt['HOST_CC'] = 'clang'
            cfgEnvDt['CXX'] = cfgEnvDt['HOST_CXX'] = 'clang++'
            if options.buildWithAsan:
                cfgEnvDt = cfgAsanParams(cfgEnvDt, options)
            cfgEnvDt['CC'] = cfgEnvDt['CC'] + CLANG_PARAMS + ' -arch i386'
            cfgEnvDt['CXX'] = cfgEnvDt['CXX'] + CLANG_PARAMS + ' -arch i386'
            cfgEnvDt['HOST_CC'] = cfgEnvDt['HOST_CC'] + CLANG_PARAMS
            cfgEnvDt['HOST_CXX'] = cfgEnvDt['HOST_CXX'] + CLANG_PARAMS
            cfgEnvDt['RANLIB'] = 'ranlib'
            cfgEnvDt['AR'] = 'ar'
            cfgEnvDt['AS'] = '$CC'
            cfgEnvDt['LD'] = 'ld'
            cfgEnvDt['STRIP'] = 'strip -x -S'
            cfgEnvDt['CROSS_COMPILE'] = '1'
            cfgCmdList.append('sh')
            if binToBeCompiled == 'nspr':
                cfgCmdList.append(os.path.normpath(shell.getNsprCfgPath()))
            else:
                cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
            cfgCmdList.append('--target=i386-apple-darwin9.2.0')  # Leopard 10.5.2
            cfgCmdList.append('--enable-macos-target=10.5')
            if options.buildWithAsan:
                cfgCmdList.append('--enable-address-sanitizer')
        # 32-bit shell on 32/64-bit x86 Linux
        elif isLinux and os.uname()[4] != 'armv7l':
            # apt-get `ia32-libs gcc-multilib g++-multilib` first, if on 64-bit Linux.
            cfgEnvDt['PKG_CONFIG_LIBDIR'] = '/usr/lib/pkgconfig'
            cfgEnvDt['CC'] = 'gcc -m32'
            cfgEnvDt['CXX'] = 'g++ -m32'
            # We might still be using GCC on Linux 32-bit, don't use clang unless Asan is specified
            if options.buildWithAsan:
                cfgEnvDt = cfgAsanParams(cfgEnvDt, options)
                cfgEnvDt['CC'] = cfgEnvDt['CC'] + CLANG_PARAMS + ' -arch i386'
                cfgEnvDt['CXX'] = cfgEnvDt['CXX'] + CLANG_PARAMS + ' -arch i386'
            cfgEnvDt['AR'] = 'ar'
            cfgCmdList.append('sh')
            if binToBeCompiled == 'nspr':
                cfgCmdList.append(os.path.normpath(shell.getNsprCfgPath()))
            else:
                cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
            cfgCmdList.append('--target=i686-pc-linux')
            if options.buildWithAsan:
                cfgCmdList.append('--enable-address-sanitizer')
        # 32-bit shell on ARM (non-tegra ubuntu)
        elif os.uname()[4] == 'armv7l':
            assert False, 'These old configuration parameters were for the old Tegra 250 board.'
            cfgEnvDt['CC'] = '/opt/cs2007q3/bin/gcc'
            cfgEnvDt['CXX'] = '/opt/cs2007q3/bin/g++'
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
        else:
            cfgCmdList.append('sh')
            if binToBeCompiled == 'nspr':
                cfgCmdList.append(os.path.normpath(shell.getNsprCfgPath()))
            else:
                cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
    # 64-bit shell on Mac OS X 10.7 Lion and greater
    elif isMac and macVer() >= [10, 7] and options.arch == '64':
        cfgEnvDt['CC'] = 'clang'
        cfgEnvDt['CXX'] = 'clang++'
        if options.buildWithAsan:
            cfgEnvDt = cfgAsanParams(cfgEnvDt, options)
        cfgEnvDt['CC'] = cfgEnvDt['CC'] + CLANG_PARAMS
        cfgEnvDt['CXX'] = cfgEnvDt['CXX'] + CLANG_PARAMS
        cfgEnvDt['AR'] = 'ar'
        cfgCmdList.append('sh')
        if binToBeCompiled == 'nspr':
            cfgCmdList.append(os.path.normpath(shell.getNsprCfgPath()))
            cfgCmdList.append('--enable-64bit')
        else:
            cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
        cfgCmdList.append('--target=x86_64-apple-darwin11.4.0')  # Lion 10.7.4
        if options.buildWithAsan:
            cfgCmdList.append('--enable-address-sanitizer')

    elif isWin:
        cfgCmdList.append('sh')
        if binToBeCompiled == 'nspr':
            cfgCmdList.append(os.path.normpath(shell.getNsprCfgPath()))
            if options.arch == '32':
                cfgCmdList.append('--enable-win32-target=WIN95')
            else:
                cfgCmdList.append('--enable-64bit')
        else:
            cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
        if options.arch == '64':
            cfgCmdList.append('--host=x86_64-pc-mingw32')
            cfgCmdList.append('--target=x86_64-pc-mingw32')
    else:
        # We might still be using GCC on Linux 64-bit, so do not use clang unless Asan is specified
        if options.buildWithAsan:
            cfgEnvDt = cfgAsanParams(cfgEnvDt, options)
            cfgEnvDt['CC'] = cfgEnvDt['CC'] + CLANG_PARAMS
            cfgEnvDt['CXX'] = cfgEnvDt['CXX'] + CLANG_PARAMS
        cfgCmdList.append('sh')
        if binToBeCompiled == 'nspr':
            cfgCmdList.append(os.path.normpath(shell.getNsprCfgPath()))
            cfgCmdList.append('--enable-64bit')
        else:
            cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
        if options.buildWithAsan:
            cfgCmdList.append('--enable-address-sanitizer')

    if options.buildWithAsan:
        assert 'clang' in cfgEnvDt['CC']
        assert 'clang++' in cfgEnvDt['CXX']

    if options.compileType == 'dbg':
        # See https://hg.mozilla.org/mozilla-central/file/0a91da5f5eab/configure.in#l6894
        # Debug builds are compiled with --enable-optimize because --disable-optimize is not present.
        cfgCmdList.append('--enable-optimize')
        cfgCmdList.append('--enable-debug')
    else:
        cfgCmdList.append('--enable-optimize')
        cfgCmdList.append('--disable-debug')

    if binToBeCompiled == 'nspr':
        cfgCmdList.append('--prefix=' + \
            normExpUserPath(os.path.join(shell.getNsprObjdir(), 'dist')))
    else:
        cfgCmdList.append('--enable-profiling')  # needed to obtain backtraces on opt shells
        cfgCmdList.append('--enable-gczeal')
        cfgCmdList.append('--enable-debug-symbols')  # gets debug symbols on opt shells
        cfgCmdList.append('--enable-methodjit')  # Enabled by default now, but useful for autoBisect
        cfgCmdList.append('--enable-type-inference') # Enabled by default now, but useful for autoBisect
        cfgCmdList.append('--disable-tests')
        if options.enableMoreDeterministic:
            # Fuzzing tweaks for more useful output, implemented in bug 706433
            cfgCmdList.append('--enable-more-deterministic')
        if options.enableRootAnalysis:
            cfgCmdList.append('--enable-root-analysis')
        if options.isThreadsafe:
            cfgCmdList.append('--enable-threadsafe')
            cfgCmdList.append('--with-nspr-prefix=' + \
                normExpUserPath(os.path.join(shell.getNsprObjdir(), 'dist')))
            cfgCmdList.append('--with-nspr-cflags=-I' + \
                normExpUserPath(os.path.join(shell.getNsprObjdir(), 'dist', 'include', 'nspr')))
            cfgCmdList.append('--with-nspr-libs=' + ' '.join([
                normExpUserPath(os.path.join(shell.getNsprObjdir(), 'dist', 'lib', LIBNSPR_NAME)),
                normExpUserPath(os.path.join(shell.getNsprObjdir(), 'dist', 'lib', LIBPLDS_NAME)),
                normExpUserPath(os.path.join(shell.getNsprObjdir(), 'dist', 'lib', LIBPLC_NAME))
                ]))
        if options.buildWithVg:
            cfgCmdList.append('--enable-valgrind')

        if os.name == 'posix':
            if (isLinux and (os.uname()[4] != 'armv7l')) or isMac:
                cfgCmdList.append('--with-ccache')  # ccache does not seem to work on Mac.
            # ccache is not applicable for non-Tegra Ubuntu ARM builds.
            elif os.uname()[1] == 'tegra-ubuntu':
                cfgCmdList.append('--with-ccache')
                cfgCmdList.append('--with-arch=armv7-a')

    if os.name == 'nt':
        # FIXME: Replace this with shellify.
        counter = 0
        for entry in cfgCmdList:
            if os.sep in entry:
                assert isWin  # MozillaBuild on Windows sometimes confuses "/" and "\".
                cfgCmdList[counter] = cfgCmdList[counter].replace(os.sep, '\\\\')
            counter = counter + 1

    # Print whatever we added to the environment
    envVarList = []
    for envVar in set(cfgEnvDt.keys()) - set(origCfgEnvDt.keys()):
        strToBeAppended = envVar + '="' + cfgEnvDt[envVar] + '"' \
            if ' ' in cfgEnvDt[envVar] else envVar + '=' + cfgEnvDt[envVar]
        envVarList.append(strToBeAppended)
    vdump('Command to be run is: ' + ' '.join(envVarList) + ' ' + ' '.join(cfgCmdList))

    wDir = shell.getNsprObjdir() if binToBeCompiled == 'nspr' else shell.getJsObjdir()
    assert os.path.isdir(wDir)
    captureStdout(cfgCmdList, ignoreStderr=True, currWorkingDir=wDir, env=cfgEnvDt)

    shell.setEnvAdded(envVarList)
    shell.setEnvFull(cfgEnvDt)
    shell.setCfgCmdExclEnv(cfgCmdList)

def copyJsSrcDirs(shell):
    '''Copies required js source directories from the repoDir to the shell fuzzing path.'''
    origJsSrc = normExpUserPath(os.path.join(shell.getRepoDir(), 'js', 'src'))
    try:
        vdump('Copying the js source tree, which is located at ' + origJsSrc)
        if sys.version_info >= (2, 6):
            shutil.copytree(origJsSrc, shell.getCompilePathJsSrc(),
                            ignore=shutil.ignore_patterns(
                                'jit-test', 'jsapi-tests', 'tests', 'trace-test', 'v8',
                                'xpconnect'))
        else:
            # Remove once Python 2.5.x is no longer used.
            shutil.copytree(origJsSrc, shell.getCompilePathJsSrc())
        vdump('Finished copying the js tree')
    except OSError:
        raise Exception('Does the js source directory or the destination exist?')

    # Do not stop copying source files out until 119351:6b280e155484 is at least the minimum
    #  version required to build on all platforms.
    # m-c changeset 119049:d2cce982a7c8 requires the build/ directory to be present.
    vEnvDir = normExpUserPath(os.path.join(shell.getRepoDir(), 'build'))
    if os.path.isdir(vEnvDir):
        shutil.copytree(vEnvDir, os.path.join(shell.getCompilePathJsSrc(), os.pardir, os.pardir,
                                              'build'))
    # m-c changeset 119049:d2cce982a7c8 requires the config/ directory to be present.
    mcCfgDir = normExpUserPath(os.path.join(shell.getRepoDir(), 'config'))
    if os.path.isdir(mcCfgDir):
        shutil.copytree(mcCfgDir, os.path.join(shell.getCompilePathJsSrc(), os.pardir, os.pardir,
                                              'config'))
    # m-c changeset 119049:d2cce982a7c8 requires the python/ directory to be present.
    pyDir = normExpUserPath(os.path.join(shell.getRepoDir(), 'python'))
    if os.path.isdir(pyDir):
        shutil.copytree(pyDir, os.path.join(shell.getCompilePathJsSrc(), os.pardir, os.pardir,
                                              'python'))
    # m-c changeset 119049:d2cce982a7c8 requires the testing/mozbase/ directory to be present.
    mzBaseDir = normExpUserPath(os.path.join(shell.getRepoDir(), 'testing', 'mozbase'))
    if os.path.isdir(mzBaseDir):
        shutil.copytree(mzBaseDir, os.path.join(shell.getCompilePathJsSrc(), os.pardir, os.pardir,
                                              'testing', 'mozbase'))

    # m-c changeset 78556:b9c673621e1e requires the js/public/ directory to be present.
    jsPubDir = normExpUserPath(os.path.join(shell.getRepoDir(), 'js', 'public'))
    if os.path.isdir(jsPubDir):
        shutil.copytree(jsPubDir, os.path.join(shell.getCompilePathJsSrc(), os.pardir, 'public'))

    # m-c changeset 64572:91a8d742c509 requires the mfbt/ directory to be present.
    mfbtDir = normExpUserPath(os.path.join(shell.getRepoDir(), 'mfbt'))
    if os.path.isdir(mfbtDir):
        shutil.copytree(mfbtDir, os.path.join(shell.getCompilePathJsSrc(), os.pardir, os.pardir,
                                              'mfbt'))

    assert os.path.isdir(shell.getCompilePathJsSrc())

def compileJsCopy(shell, options):
    '''This function compiles and copies a binary.'''
    try:
        cmdList = ['make', '-C', shell.getJsObjdir(), '-j' + str(COMPILATION_JOBS), '-s']
        out = captureStdout(cmdList, combineStderr=True, ignoreExitCode=True,
                            currWorkingDir=shell.getJsObjdir())[0]
        if 'no such option: -s' in out:  # Retry only for this situation.
            cmdList.remove('-s')  # Pymake older than m-c rev 232553f741a0 did not support '-s'.
            print 'Trying once more without -s...'
            out = captureStdout(cmdList, combineStderr=True, ignoreExitCode=True,
                                currWorkingDir=shell.getJsObjdir())[0]
    except Exception, e:
        # A non-zero error can be returned during make, but eventually a shell still gets compiled.
        if os.path.exists(shell.getShellCompiledPath()):
            print 'A shell was compiled even though there was a non-zero exit code. Continuing...'
        else:
            print "`make` did not result in a js shell:"
            raise

    if os.path.exists(shell.getShellCompiledPath()):
        shutil.copy2(shell.getShellCompiledPath(), shell.getShellBaseTempDirWithName())
        assert os.path.isfile(shell.getShellBaseTempDirWithName())
    else:
        print out
        raise Exception("`make` did not result in a js shell, no exception thrown.")

def compileNspr(shell, options):
    '''Compile a NSPR binary.'''
    shutil.copytree(normExpUserPath(os.path.join(shell.getRepoDir(), 'nsprpub')),
                    shell.getCompilePathNsprSrc())
    autoconfRun(shell.getCompilePathNsprSrc())
    try:
        os.mkdir(shell.getNsprObjdir())
    except OSError:
        raise Exception('Unable to create NSPR objdir.')
    cfgBin(shell, options, 'nspr')
    nsprCmdList = ['make', '-C', shell.getNsprObjdir(), '-j' + str(COMPILATION_JOBS), '-s']
    out = captureStdout(nsprCmdList, combineStderr=True, ignoreExitCode=True,
                        currWorkingDir=shell.getNsprObjdir())[0]
    if not normExpUserPath(os.path.join(shell.getNsprObjdir(), 'dist', 'lib', LIBNSPR_NAME)):
        print out
        raise Exception("`make` did not result in a NSPR binary.")

    assert os.path.isdir(normExpUserPath(os.path.join(
        shell.getNsprObjdir(), 'dist', 'include', 'nspr')))
    assert os.path.isfile(normExpUserPath(os.path.join(
        shell.getNsprObjdir(), 'dist', 'lib', LIBNSPR_NAME)))
    assert os.path.isfile(normExpUserPath(os.path.join(
        shell.getNsprObjdir(), 'dist', 'lib', LIBPLDS_NAME)))
    assert os.path.isfile(normExpUserPath(os.path.join(
        shell.getNsprObjdir(), 'dist', 'lib', LIBPLS_NAME)))

def compileStandalone(compiledShell):
    """Compile a shell, not keeping the intermediate object files around. Used by autoBisect."""

    try:
        copyJsSrcDirs(compiledShell)
        cfgJsCompileCopy(compiledShell, compiledShell.buildOptions)
        verifyBinary(compiledShell, compiledShell.buildOptions)
        shutil.copy2(compiledShell.getShellBaseTempDirWithName(), compiledShell.getShellCachePath())
    finally:
        shutil.rmtree(compiledShell.getBaseTempDir())

def makeTestRev(options):
    def testRev(rev):
        shell = CompiledShell(options.buildOptions, rev, mkdtemp(prefix="abtmp-" + rev + "-"))
        cachedNoShell = shell.getShellCachePath() + ".busted"

        print "Rev " + rev + ":",
        if os.path.exists(shell.getShellCachePath()):
            print "Found cached shell...   Testing...",
            return options.testAndLabel(shell.getShellCachePath(), rev)
        elif os.path.exists(cachedNoShell):
            return (options.compilationFailedLabel, 'compilation failed (cached)')
        else:
            print "Updating...",
            captureStdout(["hg", "-R", options.buildOptions.repoDir] + ['update', '-r', rev], ignoreStderr=True)
            destroyPyc(options.buildOptions.repoDir)
            try:
                print "Compiling...",
                compileStandalone(shell)
            except Exception, e:
                with open(cachedNoShell, 'wb') as f:
                    f.write("Caught exception %s (%s)\n" % (repr(e), str(e)))
                    f.write("Backtrace:\n")
                    f.write(format_exc() + "\n");
                return (options.compilationFailedLabel, 'compilation failed (' + str(e) + ') (details in ' + cachedNoShell + ')')
            print "Testing...",
            return options.testAndLabel(shell.getShellCachePath(), rev)
    return testRev


def main():
    """Build a shell and place it in the autoBisect cache."""

    usage = 'Usage: %prog [options]'
    parser = OptionParser(usage)
    parser.disable_interspersed_args()

    parser.set_defaults(
        repoDir = getMcRepoDir()[1],
        buildOptions = "",
    )

    # Specify how the shell will be built.
    # See buildOptions.py for details.
    parser.add_option('-b', '--build',
                      dest='buildOptions',
                      help='Specify build options, e.g. -b "-c opt --arch=32" (python buildOptions.py --help)')

    # Specify the repository (working directory) in which to bisect.
    parser.add_option('-R', '--repoDir', dest='repoDir',
                      help='Source code directory. Defaults to "%default".')

    (options, args) = parser.parse_args()
    options.buildOptions = buildOptions.parseShellOptions(options.buildOptions)
    localOrigHgHash, localOrigHgNum, isOnDefault = getRepoHashAndId(options.buildOptions.repoDir)
    shell = CompiledShell(options.buildOptions, localOrigHgHash, mkdtemp(prefix="cshell-" + localOrigHgHash + "-"))
    compileStandalone(shell)
    print shell.getShellCachePath()

if __name__ == '__main__':
    main()

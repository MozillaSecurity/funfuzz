#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import ctypes
import os
import shutil
import subprocess
import sys

from copy import deepcopy
from multiprocessing import cpu_count
from tempfile import mkdtemp
from traceback import format_exc
from optparse import OptionParser

import buildOptions
from inspectShell import ALL_COMPILE_LIBS, ALL_RUN_LIBS
from inspectShell import RUN_NSPR_LIB, RUN_PLDS_LIB, RUN_PLC_LIB
from inspectShell import verifyBinary

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
from hgCmds import getRepoNameFromHgrc, getRepoHashAndId, destroyPyc
from subprocesses import captureStdout, isARMv7l, isLinux, isMac, isVM, isWin, macVer, \
    normExpUserPath, rmTreeIfExists, shellify, vdump

CLANG_PARAMS = ' -Qunused-arguments'
# If one wants to bisect between 97464:e077c138cd5d to 150877:c62ad7dd57cd on Windows with
# MSVC 2010, change "mozmake" in the line below back to "make".
MAKE_BINARY = 'mozmake' if isWin else 'make'
if cpu_count() > 2:
    COMPILATION_JOBS = ((cpu_count() * 5) // 4)
elif isARMv7l:
    COMPILATION_JOBS = 2  # Likely an ARM board, e.g. pandaboard
else:
    COMPILATION_JOBS = 3  # Other single/dual core computers


class CompiledShell(object):
    def __init__(self, buildOpts, hgHash):
        self.shellNameWithoutExt = buildOptions.computeShellName(buildOpts, hgHash)
        self.shellNameWithExt = self.shellNameWithoutExt + ('.exe' if isWin else '')
        self.hgHash = hgHash
        self.buildOptions = buildOpts

        self.jsObjdir = ''
        self.nsprObjdir = ''
    def setDestDir(self, tDir):
        self.destDir = tDir

        if os.name == 'nt':  # adapted from http://stackoverflow.com/a/3931799
            winTmpDir = unicode(self.destDir)
            GetLongPathName = ctypes.windll.kernel32.GetLongPathNameW
            unicodeBuffer = ctypes.create_unicode_buffer(GetLongPathName(winTmpDir, 0, 0))
            GetLongPathName(winTmpDir, unicodeBuffer, len(unicodeBuffer))
            self.destDir = normExpUserPath(str(unicodeBuffer.value)) # convert back to a str

        assert '~' not in self.destDir
        assert os.path.isdir(self.destDir)
    def getDestDir(self):
        return self.destDir
    def setCfgCmdExclEnv(self, cfg):
        self.cfg = cfg
    def getCfgCmdExclEnv(self):
        return self.cfg
    def getJsCfgPath(self):
        self.jsCfgFile = normExpUserPath(os.path.join(self.getRepoDirJsSrc(), 'configure'))
        assert os.path.isfile(self.jsCfgFile)
        return self.jsCfgFile
    def getNsprCfgPath(self):
        self.nsprCfgFile = normExpUserPath(os.path.join(self.getRepoDirNsprSrc(), 'configure'))
        assert os.path.isfile(self.nsprCfgFile)
        return self.nsprCfgFile
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
        return self.jsObjdir
    def createJsObjdir(self):
        self.jsObjdir = mkdtemp(prefix='-'.join(['js', self.buildOptions.compileType, 'objdir',
                                                 self.hgHash]) + '-')
    def getNsprObjdir(self):
        return self.nsprObjdir
    def createNsprObjdir(self):
        self.nsprObjdir = mkdtemp(prefix='-'.join(['nspr', self.buildOptions.compileType, 'objdir',
                                                   self.hgHash]) + '-')
    def getRepoDir(self):
        return self.buildOptions.repoDir
    def getRepoDirJsSrc(self):
        return normExpUserPath(os.path.join(self.getRepoDir(), 'js', 'src'))
    def getRepoDirNsprSrc(self):
        return normExpUserPath(os.path.join(self.getRepoDir(), 'nsprpub'))
    def getRepoName(self):
        return getRepoNameFromHgrc(self.buildOptions.repoDir)
    def getShellCacheDir(self):
        return normExpUserPath(os.path.join(ensureCacheDir(), self.shellNameWithoutExt))
    def getShellCacheFullPath(self):
        return normExpUserPath(os.path.join(self.getShellCacheDir(), self.shellNameWithExt))
    def getShellCompiledPath(self):
        return normExpUserPath(os.path.join(self.getJsObjdir(), 'dist', 'bin', 'js' + ('.exe' if isWin else '')))
    def getShellCompiledRunLibsPath(self):
        libsList = [
            normExpUserPath(os.path.join(self.getNsprObjdir(), 'dist', 'lib', runLib)) \
                for runLib in ALL_RUN_LIBS
        ]
        return libsList
    def getShellBaseTempDirWithName(self):
        return normExpUserPath(os.path.join(self.getDestDir(), self.shellNameWithExt))


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
    vdump('Assumed LLVM SVN version is: 185949')

    llvmRoot = normExpUserPath(options.llvmRootSrcDir)
    # FIXME: It would be friendlier to show instructions (or even offer to set up LLVM for the user,
    # with the right LLVM revision and build options). See MDN article on Firefox and Asan above.
    assert os.path.isdir(llvmRoot)
    currEnv['LLVM_ROOT'] = llvmRoot

    ccClang = os.path.join(llvmRoot, 'build', 'bin', 'clang')
    assert os.path.isfile(ccClang)
    currEnv['CC'] = ccClang + ' -fsanitize=address -Dxmalloc=myxmalloc'

    cxxClang = os.path.join(llvmRoot, 'build', 'bin', 'clang++')
    assert os.path.isfile(cxxClang)
    currEnv['CXX'] = cxxClang + ' -fsanitize=address -Dxmalloc=myxmalloc'

    return currEnv


def cfgJsCompile(shell, options):
    '''Configures, compiles and copies a js shell according to required parameters.'''
    if options.isThreadsafe:
        compileNspr(shell, options)
    autoconfRun(shell.getRepoDirJsSrc())
    shell.createJsObjdir()
    configureTryCount = 0
    while True:
        try:
            cfgBin(shell, options, 'js')
            break
        except Exception, e:
            configureTryCount += 1
            if configureTryCount > 5:
                print 'Configuration of the js binary failed 5 times.'
                raise
            # This exception message is returned from captureStdout via cfgBin.
            # No idea why this is isLinux as well..
            if isLinux or (isWin and 'Windows conftest.exe configuration permission' in repr(e)):
                print 'Trying once more...'
                continue
    compileJs(shell, options)
    verifyBinary(shell, options)


def cfgBin(shell, options, binToBeCompiled):
    '''This function configures a binary according to required parameters.'''
    cfgCmdList = []
    cfgEnvDt = deepcopy(os.environ)
    origCfgEnvDt = deepcopy(os.environ)
    cfgEnvDt['AR'] = 'ar'
    if isARMv7l:
        # 32-bit shell on ARM boards, e.g. Pandaboards.
        assert options.arch == '32', 'arm7vl boards are only 32-bit, armv8 boards will be 64-bit.'
        if not options.enableHardFp:
            cfgEnvDt['CC'] = 'gcc -mfloat-abi=softfp -B/usr/lib/gcc/arm-linux-gnueabi/4.7'
            cfgEnvDt['CXX'] = 'g++ -mfloat-abi=softfp -B/usr/lib/gcc/arm-linux-gnueabi/4.7'
        cfgCmdList.append('sh')
        if binToBeCompiled == 'nspr':
            cfgCmdList.append(os.path.normpath(shell.getNsprCfgPath()))
        else:
            cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
            # From mjrosenb: things might go wrong if these three lines are not present for
            # compiling ARM on a 64-bit host machine. Not needed if compiling on the board itself.
            #cfgCmdList.append('--target=arm-linux-gnueabi')
            #cfgCmdList.append('--with-arch=armv7-a')
            #cfgCmdList.append('--with-thumb')
        if not options.enableHardFp:
            cfgCmdList.append('--target=arm-linux-gnueabi')
    elif options.arch == '32' and os.name == 'posix':
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
        elif isLinux and not isARMv7l:
            # apt-get `lib32z1 gcc-multilib g++-multilib` first, if on 64-bit Linux.
            cfgEnvDt['PKG_CONFIG_LIBDIR'] = '/usr/lib/pkgconfig'
            cfgEnvDt['CC'] = 'gcc -m32'
            cfgEnvDt['CXX'] = 'g++ -m32'
            # We might still be using GCC on Linux 32-bit, don't use clang unless Asan is specified
            if options.buildWithAsan:
                cfgEnvDt = cfgAsanParams(cfgEnvDt, options)
                cfgEnvDt['CC'] = cfgEnvDt['CC'] + CLANG_PARAMS + ' -arch i386'
                cfgEnvDt['CXX'] = cfgEnvDt['CXX'] + CLANG_PARAMS + ' -arch i386'
            cfgCmdList.append('sh')
            if binToBeCompiled == 'nspr':
                cfgCmdList.append(os.path.normpath(shell.getNsprCfgPath()))
            else:
                cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
            cfgCmdList.append('--target=i686-pc-linux')
            if options.buildWithAsan:
                cfgCmdList.append('--enable-address-sanitizer')
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
        cfgCmdList.append('sh')
        if binToBeCompiled == 'nspr':
            cfgCmdList.append(os.path.normpath(shell.getNsprCfgPath()))
            cfgCmdList.append('--enable-64bit')
        else:
            cfgCmdList.append(os.path.normpath(shell.getJsCfgPath()))
        # 10.7.4 can still theoretically work as of end-Sep 2013, but we no longer have Lions.
        cfgCmdList.append('--target=x86_64-apple-darwin12.5.0')  # Mountain Lion 10.8.5
        # FIXME: This needs something about using the 10.8 SDK in 10.9? Ref bug 929686.
        if options.buildWithAsan:
            cfgCmdList.append('--enable-address-sanitizer')

    elif isWin:
        cfgEnvDt['MAKE'] = 'mozmake'  # Workaround for bug 948534
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

    # See https://hg.mozilla.org/mozilla-central/file/0a91da5f5eab/configure.in#l6894
    # Debug builds are compiled with --enable-optimize because --disable-optimize is not present.
    if options.buildWithVg:
        cfgCmdList.append('--enable-optimize=-O1')
    else:
        cfgCmdList.append('--enable-optimize')

    if options.compileType == 'dbg':
        cfgCmdList.append('--enable-debug')
    else:
        cfgCmdList.append('--disable-debug')

    if binToBeCompiled == 'nspr':
        cfgCmdList.append('--prefix=' + \
            normExpUserPath(os.path.join(shell.getNsprObjdir(), 'dist')))
    else:
        cfgCmdList.append('--enable-profiling')  # needed to obtain backtraces on opt shells
        cfgCmdList.append('--enable-gczeal')
        cfgCmdList.append('--enable-debug-symbols')  # gets debug symbols on opt shells
        cfgCmdList.append('--disable-tests')
        if options.enableMoreDeterministic:
            # Fuzzing tweaks for more useful output, implemented in bug 706433
            cfgCmdList.append('--enable-more-deterministic')
        if options.enableRootAnalysis:
            cfgCmdList.append('--enable-root-analysis')
        if options.disableExactRooting:
            cfgCmdList.append('--disable-exact-rooting')
        elif options.enableGcGenerational:  # GGC requires exact rooting to be enabled
            cfgCmdList.append('--enable-gcgenerational')
        if options.buildWithVg:
            cfgCmdList.append('--enable-valgrind')

        if os.name == 'posix':
            cfgCmdList.append('--with-ccache')
        if options.isThreadsafe:
            cfgCmdList.append('--enable-threadsafe')
            cfgCmdList.append('--with-nspr-prefix=' + \
                normExpUserPath(os.path.join(shell.getNsprObjdir(), 'dist')))
            cfgCmdList.append('--with-nspr-cflags=-I' + \
                normExpUserPath(os.path.join(shell.getNsprObjdir(), 'dist', 'include', 'nspr')))
            cfgCmdList.append('--with-nspr-libs=' + ' '.join([
                normExpUserPath(os.path.join(shell.getNsprObjdir(), 'dist', 'lib', compileLib)) \
                    for compileLib in ALL_COMPILE_LIBS
                ]))
        else:
            cfgCmdList.append('--disable-threadsafe')

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
    vdump('Command to be run is: ' + shellify(envVarList) + ' ' + shellify(cfgCmdList))

    wDir = shell.getNsprObjdir() if binToBeCompiled == 'nspr' else shell.getJsObjdir()
    assert os.path.isdir(wDir)
    captureStdout(cfgCmdList, ignoreStderr=True, currWorkingDir=wDir, env=cfgEnvDt)

    shell.setEnvAdded(envVarList)
    shell.setEnvFull(cfgEnvDt)
    shell.setCfgCmdExclEnv(cfgCmdList)


def compileJs(shell, options):
    '''This function compiles and copies a binary.'''
    try:
        cmdList = [MAKE_BINARY, '-C', shell.getJsObjdir(), '-j' + str(COMPILATION_JOBS), '-s']
        out = captureStdout(cmdList, combineStderr=True, ignoreExitCode=True,
                            currWorkingDir=shell.getJsObjdir(), env=shell.getEnvFull())[0]
    except Exception, e:
        # This exception message is returned from captureStdout via cmdList.
        if (isLinux or isMac) and \
            ('GCC running out of memory' in repr(e) or 'Clang running out of memory' in repr(e)):
            # FIXME: Absolute hack to retry after hitting OOM.
            print 'Trying once more due to the compiler running out of memory...'
            out = captureStdout(cmdList, combineStderr=True, ignoreExitCode=True,
                                currWorkingDir=shell.getJsObjdir(), env=shell.getEnvFull())[0]
        # A non-zero error can be returned during make, but eventually a shell still gets compiled.
        if os.path.exists(shell.getShellCompiledPath()):
            print 'A shell was compiled even though there was a non-zero exit code. Continuing...'
        else:
            print MAKE_BINARY + " did not result in a js shell:"
            raise

    if os.path.exists(shell.getShellCompiledPath()):
        shutil.copy2(shell.getShellCompiledPath(), shell.getShellBaseTempDirWithName())
        assert os.path.isfile(shell.getShellBaseTempDirWithName())
        if options.isThreadsafe:
            for runLib in shell.getShellCompiledRunLibsPath():
                shutil.copy2(runLib, shell.getDestDir())
            assert os.path.isfile(normExpUserPath(os.path.join(shell.getDestDir(), RUN_NSPR_LIB)))
            assert os.path.isfile(normExpUserPath(os.path.join(shell.getDestDir(), RUN_PLDS_LIB)))
            assert os.path.isfile(normExpUserPath(os.path.join(shell.getDestDir(), RUN_PLC_LIB)))
    else:
        print out
        raise Exception(MAKE_BINARY + " did not result in a js shell, no exception thrown.")


def compileNspr(shell, options):
    '''Compile a NSPR binary.'''
    autoconfRun(shell.getRepoDirNsprSrc())
    shell.createNsprObjdir()
    cfgBin(shell, options, 'nspr')
    # Continue to use -j1 because NSPR does not yet seem to support parallel compilation very well.
    # Even if we move to parallel compile NSPR in the future, we must beware of breaking old
    # build during bisection. Maybe find the changeset that fixes this, and if before that, use -j1,
    # and after that, use -jX ?
    nsprCmdList = [MAKE_BINARY, '-C', shell.getNsprObjdir(), '-j1', '-s']
    out = captureStdout(nsprCmdList, combineStderr=True, ignoreExitCode=True,
                        currWorkingDir=shell.getNsprObjdir(), env=shell.getEnvFull())[0]
    for compileLib in ALL_COMPILE_LIBS:
        if not normExpUserPath(os.path.join(shell.getNsprObjdir(), 'dist', 'lib', compileLib)):
            print out
            raise Exception(MAKE_BINARY + " did not result in a NSPR binary.")

    assert os.path.isdir(normExpUserPath(os.path.join(shell.getNsprObjdir(), 'dist', 'include', 'nspr')))


def compileStandalone(compiledShell):
    """Compile a shell, not keeping the intermediate object files around. Used by autoBisect."""

    try:
        if not os.path.exists(compiledShell.getShellCacheDir()):
            try:
                os.mkdir(compiledShell.getShellCacheDir())
            except OSError:
                raise Exception('Unable to create shell cache directory.')
        compiledShell.setDestDir(compiledShell.getShellCacheDir())

        cfgJsCompile(compiledShell, compiledShell.buildOptions)

    finally:
        rmTreeIfExists(compiledShell.getJsObjdir())
        rmTreeIfExists(compiledShell.getNsprObjdir())

        # In the rare case that the cache dir is created but no binaries are present, probably due
        # to harness exception.
        if os.path.isdir(compiledShell.getShellCacheDir()):
            if not os.listdir(compiledShell.getShellCacheDir()):  # True if dir is empty
                os.rmdir(compiledShell.getShellCacheDir())


def makeTestRev(options):
    def testRev(rev):
        shell = CompiledShell(options.buildOptions, rev)
        cachedNoShell = shell.getShellCacheFullPath() + ".busted"

        print "Rev " + rev + ":",
        if os.path.exists(shell.getShellCacheFullPath()):
            print "Found cached shell...   Testing...",
            return options.testAndLabel(shell.getShellCacheFullPath(), rev)
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
                if not os.path.exists(normExpUserPath(shell.getShellCacheDir())):
                    try:
                        os.mkdir(shell.getShellCacheDir())
                    except OSError:
                        print 'Unable to create shell cache directory.'
                        raise
                with open(cachedNoShell, 'wb') as f:
                    f.write("Caught exception %s (%s)\n" % (repr(e), str(e)))
                    f.write("Backtrace:\n")
                    f.write(format_exc() + "\n")
                if os.path.exists(shell.getShellCacheFullPath()):
                    print 'Stop autoBisect - a .busted file should not be generated ' + \
                                    'with a shell that has been compiled successfully.'
                    raise
                return (options.compilationFailedLabel, 'compilation failed (' + str(e) + ') (details in ' + cachedNoShell + ')')
            print "Testing...",
            return options.testAndLabel(shell.getShellCacheFullPath(), rev)
    return testRev


def main():
    """Build a shell and place it in the autoBisect cache."""

    usage = 'Usage: %prog [options]'
    parser = OptionParser(usage)
    parser.disable_interspersed_args()

    parser.set_defaults(
        buildOptions = "",
    )

    # Specify how the shell will be built.
    # See buildOptions.py for details.
    parser.add_option('-b', '--build',
                      dest='buildOptions',
                      help='Specify build options, e.g. -b "-c opt --arch=32" (python buildOptions.py --help)')

    parser.add_option('-r', '--rev',
                      dest='revision',
                      help='Specify revision to build')

    (options, args) = parser.parse_args()
    options.buildOptions = buildOptions.parseShellOptions(options.buildOptions)

    rev = options.revision

    if rev:
        shell = CompiledShell(options.buildOptions, rev)
    else:
        localOrigHgHash, localOrigHgNum, isOnDefault = \
            getRepoHashAndId(options.buildOptions.repoDir)
        shell = CompiledShell(options.buildOptions, localOrigHgHash)

    if not os.path.exists(shell.getShellCacheFullPath()):
        if rev:
            captureStdout(["hg", "-R", options.buildOptions.repoDir] + ['update', '-r', rev],
                ignoreStderr=True)
            destroyPyc(options.buildOptions.repoDir)

        compileStandalone(shell)

    print shell.getShellCacheFullPath()

if __name__ == '__main__':
    main()

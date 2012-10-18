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

from inspectShell import verifyBinary

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
from countCpus import cpuCount
from hgCmds import getRepoHashAndId, getRepoNameFromHgrc
from subprocesses import captureStdout, isLinux, isMac, isVM, isWin, macVer, normExpUserPath, vdump

class CompiledShell(object):
    def __init__(self):
        # Sets the default shell cache directory depending on the machine.
        if isVM() == ('Windows', True):
            # FIXME: Add an assertion that isVM() is a WinXP VM, and not Vista/Win7/Win8.
            # Set to root directory of Windows VM since we only test WinXP in a VM.
            # This might fail on a Vista or Win7 VM due to lack of permissions.
            # It would be good to get this machine-specific hack out of the shared file, eventually.
            self.cacheDirBase = os.path.join('c:', os.sep)
        # This particular machine has insufficient disk space on the main drive.
        elif isLinux and os.path.exists(os.sep + 'hddbackup'):
            self.cacheDirBase = os.path.join(os.sep + 'hddbackup')
        else:
            self.cacheDirBase = normExpUserPath(os.path.join('~', 'Desktop'))
        self.cacheDir = os.path.join(self.cacheDirBase, 'autobisect-cache')
        if not os.path.exists(self.cacheDir):
            os.mkdir(self.cacheDir)
        assert os.path.isdir(self.cacheDir)
    def setArch(self, arch):
        assert arch == '32' or arch == '64'
        self.arch = arch
    def getArch(self):
        return self.arch
    def setBaseTempDir(self, baseTempDir):
        self.baseTempDir = baseTempDir
    def getBaseTempDir(self):
        return self.baseTempDir
    def getCacheDirBase(self):
        return self.cacheDirBase
    def getCacheDir(self):
        return self.cacheDir
    def setCompileType(self, compileType):
        assert compileType == 'dbg' or compileType == 'opt'
        self.compileType = compileType
    def getCompileType(self):
        return self.compileType
    def setCfgCmdExclEnv(self, cfg):
        self.cfg = cfg
    def getCfgCmdExclEnv(self):
        return self.cfg
    def setEnvAdded(self, addedEnv):
        self.addedEnv = addedEnv
    def getEnvAdded(self):
        return self.addedEnv
    def setEnvFull(self, fullEnv):
        self.fullEnv = fullEnv
    def getEnvFull(self):
        return self.fullEnv
    def getCfgPath(self):
        self.cfgFile = normExpUserPath(os.path.join(self.cPathJsSrc, 'configure'))
        assert os.path.isfile(self.cfgFile)
        return self.cfgFile
    def getCompilePath(self):
        return normExpUserPath(os.path.join(self.baseTempDir, 'compilePath'))
    def getCompilePathJsSrc(self):
        self.cPathJsSrc = normExpUserPath(os.path.join(self.baseTempDir, 'compilePath', 'js', 'src'))
        return self.cPathJsSrc
    def setHgHash(self, hgHash):
        self.hgHash = hgHash
    def getHgHash(self):
        return self.hgHash
    def setHgNum(self, hashNum):
        self.hashNum = hashNum
    def getHgNum(self):
        return self.hashNum
    def getHgPrefix(self):
        if self.repoDir == None:
            raise Exception('First setRepoDir, repository directory is not yet set.')
        return ['hg', '-R', self.repoDir]
    def setName(self, options):
        sname = '-'.join(x for x in ['js', self.compileType, self.arch,
                                     'ra' if options.enableRootAnalysis else '', self.hgHash,
                                     'windows' if isWin else platform.system().lower()] if x)
        self.shellName = sname + '.exe' if isWin else sname
    def getName(self):
        return self.shellName
    def getObjdir(self):
        return normExpUserPath(os.path.join(self.baseTempDir, 'compilePath', 'js', 'src',
                                              self.compileType + '-objdir'))
    def setRepoDir(self, repoDir):
        self.repoDir = repoDir
    def getRepoDir(self):
        return self.repoDir
    def getRepoName(self):
        if self.repoDir == None:
            raise Exception('First setRepoDir, repository directory is not yet set.')
        return getRepoNameFromHgrc(self.repoDir)
    def getShellCachePath(self):
        return normExpUserPath(os.path.join(self.cacheDir, self.shellName))
    def getShellCompiledPath(self):
        return normExpUserPath(os.path.join(self.getObjdir(), 'js' + ('.exe' if isWin else '')))
    def getShellBaseTempDir(self):
        return normExpUserPath(os.path.join(self.baseTempDir, self.shellName))

def autoconfRun(cwd):
    '''Run autoconf binaries corresponding to the platform.'''
    if isMac:
        subprocess.check_call(['autoconf213'], cwd=cwd)
    elif isLinux:
        subprocess.check_call(['autoconf2.13'], cwd=cwd)
    elif isWin:
        subprocess.check_call(['sh', 'autoconf-2.13'], cwd=cwd)

def cfgCompileCopy(shell, options):
    '''Configures, compiles and copies a js shell according to required parameters.'''
    autoconfRun(shell.getCompilePathJsSrc())
    try:
        os.mkdir(shell.getObjdir())
    except OSError:
        raise Exception('Unable to create objdir.')
    try:
        cfgJsBin(shell, options)
    except Exception, e:
        # This exception message is returned from captureStdout via cfgJsBin.
        if isLinux or (isWin and 'Windows conftest.exe configuration permission' in repr(e)):
            print 'Trying once more...'
            cfgJsBin(shell, options)
        else:
            print repr(e)
            raise Exception('Configuration of the js binary failed.')
    compileCopy(shell, options)

def cfgJsBin(shell, options):
    '''This function configures a js binary according to required parameters.'''
    cfgCmdList = []
    cfgEnvDt = deepcopy(os.environ)
    origCfgEnvDt = deepcopy(os.environ)
    # For tegra Ubuntu, no special commands needed, but do install Linux prerequisites,
    # do not worry if build-dep does not work, also be sure to apt-get zip as well.
    if (shell.getArch() == '32') and (os.name == 'posix') and (os.uname()[1] != 'tegra-ubuntu'):
        # 32-bit shell on Mac OS X 10.7 Lion and greater
        if isMac:
            assert macVer() >= [10, 7]  # We no longer support Snow Leopard 10.6 and prior.
            cfgEnvDt['CC'] = 'clang -Qunused-arguments -fcolor-diagnostics -arch i386'
            cfgEnvDt['CXX'] = 'clang++ -Qunused-arguments -fcolor-diagnostics -arch i386'
            cfgEnvDt['HOST_CC'] = 'clang -Qunused-arguments -fcolor-diagnostics'
            cfgEnvDt['HOST_CXX'] = 'clang++ -Qunused-arguments -fcolor-diagnostics'
            cfgEnvDt['RANLIB'] = 'ranlib'
            cfgEnvDt['AR'] = 'ar'
            cfgEnvDt['AS'] = '$CC'
            cfgEnvDt['LD'] = 'ld'
            cfgEnvDt['STRIP'] = 'strip -x -S'
            cfgEnvDt['CROSS_COMPILE'] = '1'
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(shell.getCfgPath()))
            cfgCmdList.append('--target=i386-apple-darwin9.2.0')  # Leopard 10.5.2
            cfgCmdList.append('--enable-macos-target=10.5')
        # 32-bit shell on 32/64-bit x86 Linux
        elif isLinux and (os.uname()[4] != 'armv7l'):
            # apt-get `ia32-libs gcc-multilib g++-multilib` first, if on 64-bit Linux.
            cfgEnvDt['PKG_CONFIG_LIBDIR'] = '/usr/lib/pkgconfig'
            cfgEnvDt['CC'] = 'gcc -m32'
            cfgEnvDt['CXX'] = 'g++ -m32'
            cfgEnvDt['AR'] = 'ar'
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(shell.getCfgPath()))
            cfgCmdList.append('--target=i686-pc-linux')
        # 32-bit shell on ARM (non-tegra ubuntu)
        elif os.uname()[4] == 'armv7l':
            assert False, 'These old configuration parameters were for the old Tegra 250 board.'
            cfgEnvDt['CC'] = '/opt/cs2007q3/bin/gcc'
            cfgEnvDt['CXX'] = '/opt/cs2007q3/bin/g++'
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(shell.getCfgPath()))
        else:
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(shell.getCfgPath()))
    # 64-bit shell on Mac OS X 10.7 Lion and greater
    elif isMac and macVer() >= [10, 7] and shell.getArch() == '64':
        cfgEnvDt['CC'] = 'clang -Qunused-arguments -fcolor-diagnostics'
        cfgEnvDt['CXX'] = 'clang++ -Qunused-arguments -fcolor-diagnostics'
        cfgEnvDt['AR'] = 'ar'
        cfgCmdList.append('sh')
        cfgCmdList.append(os.path.normpath(shell.getCfgPath()))
        cfgCmdList.append('--target=x86_64-apple-darwin11.4.0')  # Lion 10.7.4
    elif isWin and shell.getArch() == '64':
        cfgCmdList.append('sh')
        cfgCmdList.append(os.path.normpath(shell.getCfgPath()))
        cfgCmdList.append('--host=x86_64-pc-mingw32')
        cfgCmdList.append('--target=x86_64-pc-mingw32')
    else:
        cfgCmdList.append('sh')
        cfgCmdList.append(os.path.normpath(shell.getCfgPath()))

    if shell.getCompileType() == 'dbg':
        cfgCmdList.append('--disable-optimize')
        cfgCmdList.append('--enable-debug')
    elif shell.getCompileType() == 'opt':
        cfgCmdList.append('--enable-optimize')
        cfgCmdList.append('--disable-debug')
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
        cfgCmdList.append('--with-system-nspr')

    if os.name == 'posix':
        if (isLinux and (os.uname()[4] != 'armv7l')) or isMac:
            cfgCmdList.append('--enable-valgrind')
            if isLinux:
                cfgCmdList.append('--with-ccache')  # ccache does not seem to work on Mac.
        # ccache is not applicable for non-Tegra Ubuntu ARM builds.
        elif os.uname()[1] == 'tegra-ubuntu':
            cfgCmdList.append('--with-ccache')
            cfgCmdList.append('--with-arch=armv7-a')
    else:
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
    assert os.path.isdir(shell.getObjdir())
    vdump('Command to be run is: ' + ' '.join(envVarList) + ' '.join(cfgCmdList))
    out = captureStdout(cfgCmdList, ignoreStderr=True, currWorkingDir=shell.getObjdir(),
                        env=cfgEnvDt)

    shell.setEnvAdded(envVarList)
    shell.setEnvFull(cfgEnvDt)
    shell.setCfgCmdExclEnv(cfgCmdList)

def copyJsSrcDirs(shell):
    '''Copies required js source directories from the shell repoDir to the shell fuzzing path.'''
    cPath = normExpUserPath(os.path.join(shell.getBaseTempDir(), 'compilePath', 'js', 'src'))
    origJsSrc = normExpUserPath(os.path.join(shell.getRepoDir(), 'js', 'src'))
    try:
        vdump('Copying the js source tree, which is located at ' + origJsSrc)
        if sys.version_info >= (2, 6):
            shutil.copytree(origJsSrc, shell.getCompilePathJsSrc(),
                            ignore=shutil.ignore_patterns(
                                'jit-test', 'tests', 'trace-test', 'xpconnect'))
        else:
            # Remove once Python 2.5.x is no longer used.
            shutil.copytree(origJsSrc, shell.getCompilePathJsSrc())
        vdump('Finished copying the js tree')
    except OSError:
        raise Exception('Do the js source directory or the destination exist?')

    # 91a8d742c509 introduced a mfbt directory on the same level as the js/ directory.
    mfbtDir = normExpUserPath(os.path.join(shell.getRepoDir(), 'mfbt'))
    if os.path.isdir(mfbtDir):
        shutil.copytree(mfbtDir, os.path.join(shell.getCompilePathJsSrc(), os.pardir, os.pardir,
                                              'mfbt'))

    # b9c673621e1e introduced a public directory on the same level as the js/src directory.
    jsPubDir = normExpUserPath(os.path.join(shell.getRepoDir(), 'js', 'public'))
    if os.path.isdir(jsPubDir):
        shutil.copytree(jsPubDir, os.path.join(shell.getCompilePathJsSrc(), os.pardir, 'public'))

    assert os.path.isdir(shell.getCompilePathJsSrc())

def compileCopy(shell, options):
    '''This function compiles and copies a binary.'''
    # Replace cpuCount() with multiprocessing's cpu_count() once Python 2.6 is in all build slaves.
    jobs = ((cpuCount() * 5) // 4) if cpuCount() > 2 else 3
    try:
        cmdList = ['make', '-C', shell.getObjdir(), '-j' + str(jobs), '-s']
        out = captureStdout(cmdList, combineStderr=True, ignoreExitCode=True,
                            currWorkingDir=shell.getObjdir())[0]
        if 'no such option: -s' in out:  # Retry only for this situation.
            cmdList.remove('-s')  # Pymake older than m-c rev 232553f741a0 did not support '-s'.
            print 'Trying once more without -s...'
            out = captureStdout(cmdList, combineStderr=True, ignoreExitCode=True,
                                currWorkingDir=shell.getObjdir())[0]
    except Exception, e:
        # A non-zero error can be returned during make, but eventually a shell still gets compiled.
        if os.path.exists(shell.getShellCompiledPath()):
            print 'A shell was compiled even though there was a non-zero exit code. Continuing...'
        else:
            raise Exception("`make` did not result in a js shell, '" + repr(e) + "' thrown.")

    if os.path.exists(shell.getShellCompiledPath()):
        shell.setName(options)
        shutil.copy2(shell.getShellCompiledPath(), shell.getShellBaseTempDir())
        assert os.path.isfile(shell.getShellBaseTempDir())
    else:
        print out
        raise Exception("`make` did not result in a js shell, no exception thrown.")

def makeTestRev(shell, options):
    '''Calls recursive function testRev to keep compiling and testing changesets until it stops.'''
    def testRev(rev):
        shell.setHgHash(rev)
        shell.setName(options)
        cachedNoShell = shell.getShellCachePath() + ".busted"

        print "Rev " + rev + ":",
        if os.path.exists(shell.getShellCachePath()):
            print "Found cached shell...   ",
        elif os.path.exists(cachedNoShell):
            return (options.compilationFailedLabel, 'compilation failed (cached)')
        else:
            print "Updating...",
            shell.setBaseTempDir(mkdtemp(prefix="abtmp-" + rev + "-"))
            captureStdout(shell.getHgPrefix() + ['update', '-r', rev], ignoreStderr=True)
            try:
                print "Compiling...",
                copyJsSrcDirs(shell)
                cfgCompileCopy(shell, options)
                verifyBinary(shell, options)
                shutil.copy2(shell.getShellBaseTempDir(), shell.getShellCachePath())
            except Exception, e:
                with open(cachedNoShell, 'wb') as f:
                    f.write("Caught exception %s (%s)\n" % (repr(e), str(e)))
                    f.write("Backtrace:\n")
                    f.write(format_exc() + "\n");
                return (options.compilationFailedLabel, 'compilation failed (' + str(e) + ')')

        print "Testing...",
        return options.testAndLabel(shell)
    return testRev

if __name__ == '__main__':
    pass

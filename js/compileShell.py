#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import platform
import subprocess
import shutil
import sys

from traceback import format_exc

path0 = os.path.dirname(__file__)
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
from subprocesses import captureStdout, macType, normExpUserPath, vdump
from countCpus import cpuCount

def hgHashAddToFuzzPath(fuzzPath, repoDir):
    '''
    This function finds the mercurial revision and appends it to the directory name.
    It also prompts if the user wants to continue, should the repository not be on tip.
    '''
    hgIdCmdList = ['hg', 'identify', '-i', '-n', '-b', repoDir]
    vdump('About to start running `' + ' '.join(hgIdCmdList) + '` ...')
    # In Windows, this throws up a warning about failing to set color mode to win32.
    if platform.system() == 'Windows':
        hgIdFull = captureStdout(hgIdCmdList, currWorkingDir=repoDir, ignoreStderr=True)[0]
    else:
        hgIdFull = captureStdout(hgIdCmdList, currWorkingDir=repoDir)[0]
    hgIdChangesetHash = hgIdFull.split(' ')[0]
    hgIdLocalNum = hgIdFull.split(' ')[1]
    # In Windows, this throws up a warning about failing to set color mode to win32.
    if platform.system() == 'Windows':
        hgIdBranch = captureStdout(['hg', 'id', '-t'], currWorkingDir=repoDir, ignoreStderr=True)[0]
    else:
        hgIdBranch = captureStdout(['hg', 'id', '-t'], currWorkingDir=repoDir)[0]
    onDefaultTip = True
    if 'tip' not in hgIdBranch:
        print 'The repository is at this changeset -', hgIdLocalNum + ':' + hgIdChangesetHash
        notOnDefaultTipApproval = str(
            raw_input('Not on default tip! Are you sure you want to continue? (y/n): '))
        if notOnDefaultTipApproval == ('y' or 'yes'):
            onDefaultTip = False
        else:
            switchToDefaultTipApproval = str(
                raw_input('Do you want to switch to the default tip? (y/n): '))
            if switchToDefaultTipApproval == ('y' or 'yes'):
                subprocess.check_call(['hg', 'up', 'default'], cwd=repoDir)
            else:
                raise Exception('Not on default tip.')
    fuzzPath = '-'.join([fuzzPath, hgIdLocalNum, hgIdChangesetHash])
    vdump('Finished running `' + ' '.join(hgIdCmdList) + '`.')
    return normExpUserPath(fuzzPath), onDefaultTip

def patchHgRepoUsingMq(patchLoc, cwd=os.getcwdu()):
    # We may have passed in the patch with or without the full directory.
    p = os.path.abspath(normExpUserPath(patchLoc))
    pname = os.path.basename(p)
    assert (p, pname) != ('','')
    subprocess.check_call(['hg', 'qimport', p], cwd=cwd)
    vdump("Patch qimport'ed.")
    try:
        subprocess.check_call(['hg', 'qpush', pname], cwd=cwd)
        vdump("Patch qpush'ed.")
    except subprocess.CalledProcessError:
        subprocess.check_call(['hg', 'qpop'], cwd=cwd)
        subprocess.check_call(['hg', 'qdelete', pname], cwd=cwd)
        print 'You may have untracked .rej files in the repository.'
        print '`hg st` output of the repository in ' + cwd + ' :'
        subprocess.check_call(['hg', 'st'], cwd=cwd)
        hgPurgeAns = str(raw_input('Do you want to run `hg purge`? (y/n): '))
        assert hgPurgeAns.lower() in ('y', 'n')
        if hgPurgeAns == 'y':
            subprocess.check_call(['hg', 'purge'], cwd=cwd)
        raise Exception(format_exc())
    return pname

def autoconfRun(cwd):
    '''
    Sniff platform and run different autoconf types:
    '''
    if platform.system() == 'Darwin':
        subprocess.check_call(['autoconf213'], cwd=cwd)
    elif platform.system() == 'Linux':
        subprocess.check_call(['autoconf2.13'], cwd=cwd)
    elif platform.system() == 'Windows':
        subprocess.check_call(['sh', 'autoconf-2.13'], cwd=cwd)

def cfgJsBin(archNum, compileType, threadsafe, configure, objdir):
    '''
    This function configures a js binary depending on the parameters.
    '''
    cfgCmdList = []
    cfgEnvList = os.environ
    # For tegra Ubuntu, no special commands needed, but do install Linux prerequisites,
    # do not worry if build-dep does not work, also be sure to apt-get zip as well.
    if (archNum == '32') and (os.name == 'posix') and (os.uname()[1] != 'tegra-ubuntu'):
        # 32-bit shell on Mac OS X 10.6
        if macType() == (True, True, False):
            cfgEnvList['CC'] = 'gcc-4.2 -arch i386'
            cfgEnvList['CXX'] = 'g++-4.2 -arch i386'
            cfgEnvList['HOST_CC'] = 'gcc-4.2'
            cfgEnvList['HOST_CXX'] = 'g++-4.2'
            cfgEnvList['RANLIB'] = 'ranlib'
            cfgEnvList['AR'] = 'ar'
            cfgEnvList['AS'] = '$CC'
            cfgEnvList['LD'] = 'ld'
            cfgEnvList['STRIP'] = 'strip -x -S'
            cfgEnvList['CROSS_COMPILE'] = '1'
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(configure))
            cfgCmdList.append('--target=i386-apple-darwin8.0.0')
        # 32-bit shell on Mac OS X 10.7 Lion
        elif macType() == (True, False, True):
            cfgEnvList['CC'] = 'clang -Qunused-arguments -fcolor-diagnostics -arch i386'
            cfgEnvList['CXX'] = 'clang++ -Qunused-arguments -fcolor-diagnostics -arch i386'
            cfgEnvList['HOST_CC'] = 'clang -Qunused-arguments -fcolor-diagnostics'
            cfgEnvList['HOST_CXX'] = 'clang++ -Qunused-arguments -fcolor-diagnostics'
            cfgEnvList['RANLIB'] = 'ranlib'
            cfgEnvList['AR'] = 'ar'
            cfgEnvList['AS'] = '$CC'
            cfgEnvList['LD'] = 'ld'
            cfgEnvList['STRIP'] = 'strip -x -S'
            cfgEnvList['CROSS_COMPILE'] = '1'
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(configure))
            cfgCmdList.append('--target=i386-apple-darwin8.0.0')
        # 32-bit shell on 32/64-bit x86 Linux
        elif (os.uname()[0] == "Linux") and (os.uname()[4] != 'armv7l'):
            # apt-get `ia32-libs gcc-multilib g++-multilib` first, if on 64-bit Linux.
            cfgEnvList['PKG_CONFIG_LIBDIR'] = '/usr/lib/pkgconfig'
            cfgEnvList['CC'] = 'gcc -m32'
            cfgEnvList['CXX'] = 'g++ -m32'
            cfgEnvList['AR'] = 'ar'
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(configure))
            cfgCmdList.append('--target=i686-pc-linux')
        # 32-bit shell on ARM (non-tegra ubuntu)
        elif os.uname()[4] == 'armv7l':
            cfgEnvList['CC'] = '/opt/cs2007q3/bin/gcc'
            cfgEnvList['CXX'] = '/opt/cs2007q3/bin/g++'
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(configure))
        else:
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(configure))
    # 64-bit shell on Mac OS X 10.7 Lion
    elif (archNum == '64') and (macType() == (True, False, True)):
        cfgEnvList['CC'] = 'clang -Qunused-arguments -fcolor-diagnostics'
        cfgEnvList['CXX'] = 'clang++ -Qunused-arguments -fcolor-diagnostics'
        cfgEnvList['AR'] = 'ar'
        cfgCmdList.append('sh')
        cfgCmdList.append(os.path.normpath(configure))
        cfgCmdList.append('--target=x86_64-apple-darwin11.2.0')
    elif (archNum == '64') and (os.name == 'nt'):
        cfgCmdList.append('sh')
        cfgCmdList.append(os.path.normpath(configure))
        cfgCmdList.append('--host=x86_64-pc-mingw32')
        cfgCmdList.append('--target=x86_64-pc-mingw32')
    else:
        cfgCmdList.append('sh')
        cfgCmdList.append(os.path.normpath(configure))

    if compileType == 'dbg':
        cfgCmdList.append('--disable-optimize')
        cfgCmdList.append('--enable-debug')
    elif compileType == 'opt':
        cfgCmdList.append('--enable-optimize')
        cfgCmdList.append('--disable-debug')
        cfgCmdList.append('--enable-profiling')  # needed to obtain backtraces on opt shells

    cfgCmdList.append('--enable-methodjit')  # Enabled by default now, but useful for autoBisect
    cfgCmdList.append('--enable-type-inference') # Enabled by default now, but useful for autoBisect
    # Fuzzing tweaks for more useful output, implemented in bug 706433
    cfgCmdList.append('--enable-more-deterministic')
    cfgCmdList.append('--disable-tests')

    if os.name != 'nt':
        if ((os.uname()[0] == "Linux") and (os.uname()[4] != 'armv7l')) or macType()[0] == True:
            cfgCmdList.append('--enable-valgrind')
            # ccache does not seem to work on Mac.
            if macType()[0] == False:
                cfgCmdList.append('--with-ccache')
        # ccache is not applicable for Windows and non-Tegra Ubuntu ARM builds.
        elif os.uname()[1] == 'tegra-ubuntu':
            cfgCmdList.append('--with-ccache')
            cfgCmdList.append('--with-arch=armv7-a')

    if threadsafe:
        cfgCmdList.append('--enable-threadsafe')
        cfgCmdList.append('--with-system-nspr')
    # Works-around "../editline/libeditline.a: No such file or directory" build errors by using
    # readline instead of editline.
    #cfgCmdList.append('--enable-readline')

    if os.name == 'nt':
        # Only tested to work for pymake.
        counter = 0
        for entry in cfgCmdList:
            if os.sep in entry:
                cfgCmdList[counter] = cfgCmdList[counter].replace(os.sep, '\\\\')
            counter = counter + 1

    captureStdout(cfgCmdList, ignoreStderr=True, currWorkingDir=objdir, env=cfgEnvList)

def shellName(archNum, compileType, extraID, vgSupport):
    sname = '-'.join(x for x in ['js', compileType, archNum, "vg" if vgSupport else "", extraID,
                                 platform.system().lower()] if x)
    ext = '.exe' if platform.system() == 'Windows' else ''
    return sname + ext

def compileCopy(archNum, compileType, extraID, usePymake, repoDir, destDir, objDir, vgSupport):
    '''
    This function compiles and copies a binary.
    '''
    # Replace cpuCount() with cpu_count from the multiprocessing library once Python 2.6 is in
    # all build machines.
    jobs = (cpuCount() * 3) // 2
    compiledNamePath = normExpUserPath(
        os.path.join(objDir, 'js' + ('.exe' if platform.system() == 'Windows' else '')))
    try:
        if usePymake:
            out = captureStdout(
                ['python', '-OO',
                 os.path.normpath(os.path.join(repoDir, 'build', 'pymake', 'make.py')),
                 '-j' + str(jobs), '-s'], combineStderr=True, currWorkingDir=objDir)[0]
            # Pymake in builds earlier than revision 232553f741a0 did not support the '-s' option.
            if 'no such option: -s' in out:
                out = captureStdout(
                    ['python', '-OO',
                     os.path.normpath(os.path.join(repoDir, 'build', 'pymake', 'make.py')),
                     '-j' + str(jobs)], combineStderr=True, currWorkingDir=objDir)[0]
        else:
            out = captureStdout(
                ['make', '-C', objDir, '-j' + str(jobs), '-s'],
                combineStderr=True, ignoreExitCode=True, currWorkingDir=objDir)[0]
    except Exception:
        # Sometimes a non-zero error can be returned during the make process, but eventually a
        # shell still gets compiled.
        if os.path.exists(compiledNamePath):
            print 'A shell was compiled even though there was a non-zero exit code. Continuing...'
        else:
            print out
            raise Exception("`make` did not result in a js shell, '" + repr(e) + "' thrown.")

    if not os.path.exists(compiledNamePath):
        print out
        raise Exception("`make` did not result in a js shell, no exception thrown.")
    else:
        newNamePath = normExpUserPath(
            os.path.join(destDir, shellName(archNum, compileType, extraID, vgSupport)))
        shutil.copy2(compiledNamePath, newNamePath)
        return newNamePath

if __name__ == '__main__':
    pass

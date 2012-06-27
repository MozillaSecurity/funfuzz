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

from copy import deepcopy
from traceback import format_exc

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
from countCpus import cpuCount
from subprocesses import captureStdout, macType, normExpUserPath, vdump

def getRepoHashAndId(repoDir):
    '''
    This function returns the repository hash and id, and whether it is on default.
    It also asks what the user would like to do, should the repository not be on default.
    '''
    # This returns null if the repository is not on default.
    hgLogTmplList = ['hg', 'log', '-r', '"parents() and default"',
                     '--template', '"{node|short} {rev}"']
    hgIdFull = captureStdout(hgLogTmplList, currWorkingDir=repoDir)[0]
    onDefault = bool(hgIdFull)
    if not onDefault:
        updateDefault = raw_input('Not on default tip! ' + \
            'Would you like to (a)bort, update to (d)efault, or (u)se this rev: ')
        if updateDefault == 'a':
            print 'Aborting...'
            sys.exit(0)
        elif updateDefault == 'd':
            subprocess.check_call(['hg', 'up', 'default'], cwd=repoDir)
            onDefault = True
        elif updateDefault == 'u':
            hgLogTmplList = ['hg', 'log', '-r', 'parents()', '--template', '{node|short} {rev}']
        else:
            raise Exception('Invalid choice.')
        hgIdFull = captureStdout(hgLogTmplList, currWorkingDir=repoDir)[0]
    assert hgIdFull != ''
    (hgIdChangesetHash, hgIdLocalNum) = hgIdFull.split(' ')
    vdump('Finished getting the hash and local id number of the repository.')
    return hgIdChangesetHash, hgIdLocalNum, onDefault

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
    cfgEnvDt = deepcopy(os.environ)
    origCfgEnvDt = deepcopy(os.environ)
    # For tegra Ubuntu, no special commands needed, but do install Linux prerequisites,
    # do not worry if build-dep does not work, also be sure to apt-get zip as well.
    if (archNum == '32') and (os.name == 'posix') and (os.uname()[1] != 'tegra-ubuntu'):
        # 32-bit shell on Mac OS X 10.6
        if macType() == (True, True, False):
            cfgEnvDt['CC'] = 'gcc-4.2 -arch i386'
            cfgEnvDt['CXX'] = 'g++-4.2 -arch i386'
            cfgEnvDt['HOST_CC'] = 'gcc-4.2'
            cfgEnvDt['HOST_CXX'] = 'g++-4.2'
            cfgEnvDt['RANLIB'] = 'ranlib'
            cfgEnvDt['AR'] = 'ar'
            cfgEnvDt['AS'] = '$CC'
            cfgEnvDt['LD'] = 'ld'
            cfgEnvDt['STRIP'] = 'strip -x -S'
            cfgEnvDt['CROSS_COMPILE'] = '1'
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(configure))
            cfgCmdList.append('--target=i386-apple-darwin8.0.0')
        # 32-bit shell on Mac OS X 10.7 Lion
        elif macType() == (True, False, True):
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
            cfgCmdList.append(os.path.normpath(configure))
            cfgCmdList.append('--target=i386-apple-darwin8.0.0')
        # 32-bit shell on 32/64-bit x86 Linux
        elif (os.uname()[0] == "Linux") and (os.uname()[4] != 'armv7l'):
            # apt-get `ia32-libs gcc-multilib g++-multilib` first, if on 64-bit Linux.
            cfgEnvDt['PKG_CONFIG_LIBDIR'] = '/usr/lib/pkgconfig'
            cfgEnvDt['CC'] = 'gcc -m32'
            cfgEnvDt['CXX'] = 'g++ -m32'
            cfgEnvDt['AR'] = 'ar'
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(configure))
            cfgCmdList.append('--target=i686-pc-linux')
        # 32-bit shell on ARM (non-tegra ubuntu)
        elif os.uname()[4] == 'armv7l':
            cfgEnvDt['CC'] = '/opt/cs2007q3/bin/gcc'
            cfgEnvDt['CXX'] = '/opt/cs2007q3/bin/g++'
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(configure))
        else:
            cfgCmdList.append('sh')
            cfgCmdList.append(os.path.normpath(configure))
    # 64-bit shell on Mac OS X 10.7 Lion
    elif (archNum == '64') and (macType() == (True, False, True)):
        cfgEnvDt['CC'] = 'clang -Qunused-arguments -fcolor-diagnostics'
        cfgEnvDt['CXX'] = 'clang++ -Qunused-arguments -fcolor-diagnostics'
        cfgEnvDt['AR'] = 'ar'
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
        cfgCmdList.append('--enable-gczeal')

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

    # Print whatever we added to the environment
    envVarList = []
    for envVar in set(cfgEnvDt.keys()) - set(origCfgEnvDt.keys()):
        strToBeAppended = envVar + '="' + cfgEnvDt[envVar] + '"' \
            if ' ' in cfgEnvDt[envVar] else envVar + '=' + cfgEnvDt[envVar]
        envVarList.append(strToBeAppended)
    vdump('Environment variables added are: ' + ' '.join(envVarList))

    out = captureStdout(cfgCmdList, ignoreStderr=True, currWorkingDir=objdir, env=cfgEnvDt)

    return out, envVarList, cfgEnvDt, cfgCmdList

def shellName(archNum, compileType, extraID, vgSupport):
    sname = '-'.join(x for x in ['js', compileType, archNum, "vg" if vgSupport else "", extraID,
                                 platform.system().lower()] if x)
    ext = '.exe' if platform.system() == 'Windows' else ''
    return sname + ext

def compileCopy(archNum, compileType, extraID, usePymake, repoDir, destDir, objDir, vgSupport):
    '''
    This function compiles and copies a binary.
    '''
    # Replace cpuCount() with multiprocessing's cpu_count() once Python 2.6 is in all build slaves.
    jobs = (cpuCount() * 3) // 2
    compiledNamePath = normExpUserPath(
        os.path.join(objDir, 'js' + ('.exe' if platform.system() == 'Windows' else '')))
    try:
        cmdList = []
        ignoreECode = False
        if usePymake:
            cmdList = ['python', '-OO',
                     os.path.normpath(os.path.join(repoDir, 'build', 'pymake', 'make.py')),
                     '-j' + str(jobs), '-s']
        else:
            cmdList = ['make', '-C', objDir, '-s']
            ignoreECode = True
            if platform.system() != 'Windows':
                cmdList.append('-j' + str(jobs))  # Win needs pymake for multicore compiles.
        vdump('cmdList from compileCopy is: ' + ' '.join(cmdList))
        out = captureStdout(cmdList, combineStderr=True, ignoreExitCode=ignoreECode,
                            currWorkingDir=objDir)[0]
        if usePymake and 'no such option: -s' in out:  # Retry only for this situation.
            cmdList.remove('-s')  # Pymake older than m-c rev 232553f741a0 did not support '-s'.
            print 'Trying once more without -s...'
            vdump('cmdList from compileCopy is: ' + ' '.join(cmdList))
            out = captureStdout(cmdList, combineStderr=True, ignoreExitCode=ignoreECode,
                                currWorkingDir=objDir)[0]
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

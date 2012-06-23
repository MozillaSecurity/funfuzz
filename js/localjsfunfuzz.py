#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import with_statement

import os
import platform
import pdb  # needed for Windows debugging of intermittent conftest error.
import shutil
import subprocess
import sys

from ConfigParser import SafeConfigParser
from random import randint
from optparse import OptionParser
from tempfile import mkdtemp
from compileShell import getRepoHashAndId, patchHgRepoUsingMq, autoconfRun, cfgJsBin, compileCopy
from inspectShell import archOfBinary, testDbgOrOpt

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
from subprocesses import captureStdout, dateStr, isVM, normExpUserPath, verbose, vdump
from fileIngredients import fileContains
from downloadBuild import downloadBuild, downloadLatestBuild, mozPlatform

def machineTypeDefaults(timeout):
    '''
    Sets different defaults depending on the machine type.
    '''
    if platform.uname()[1] == 'tegra-ubuntu':
        return '180'
    elif platform.uname()[4] == 'armv7l':
        return '600'
    else:
        return timeout

def parseOptions():
    usage = 'Usage: %prog [options]'
    parser = OptionParser(usage)

    parser.set_defaults(
        disableCompareJIT = False,
        disableRndFlags = False,
        disableStartFuzzing = False,
        archType = '32',
        shellType = 'dbg,opt',
        shellflags = '',
        srcRepo = '~/trees/mozilla-central',
        timeout = 10,
        enablePymake = True if platform.system == 'Windows' else False,
        enableTs = False,
        enableVg = False,
    )

    parser.add_option('--disable-comparejit', dest='disableCompareJIT', action='store_true',
                      help='Disable comparejit fuzzing.')
    parser.add_option('--disable-random-flags', dest='disableRndFlags', action='store_true',
                      help='Disable random flag fuzzing.')
    parser.add_option('--disable-start-fuzzing', dest='disableStartFuzzing', action='store_true',
                      help='Compile shells only, do not start fuzzing.')

    parser.add_option('-a', '--set-archtype', dest='archType',
                      help='Sets the shell architecture to be fuzzed. Defaults to "%default".')
    parser.add_option('-c', '--set-shelltype', dest='shellType',
                      # FIXME: This should be improved. Seems like a hackish way.
                      help='Sets the shell type to be fuzzed. Defaults to "dbg". Note that both ' + \
                           'debug and opt will be compiled by default for easy future testing.')
    parser.add_option('-f', '--set-shellflags', dest='shellflags',
                      # This is not set to %default because of the upcoming revamp of --random-flags
                      help='Sets the flags for the shell. Defaults to [-m, -a, -n, [-d if debug]].')
    parser.add_option('-r', '--set-src-repo', dest='srcRepo',
                      help='Sets the source repository. Defaults to "%default".')
    parser.add_option('-t', '--set-loop-timeout', type='int', dest='timeout',
                      help='Sets the timeout for loopjsfunfuzz.py. ' + \
                           'Defaults to "180" seconds for tegra-ubuntu machines. ' + \
                           'Defaults to "300" seconds when Valgrind is turned on. ' + \
                           'Defaults to "600" seconds for arm7l machines. ' + \
                           'Defaults to "%default" seconds for all other machines.')

    parser.add_option('-p', '--enable-patch-dir', dest='patchdir',
                      #help='Define the path to a single patch or to a directory containing mq ' + \
                      #     'patches. Must have a "series" file present, containing the names ' + \
                      #     'of the patches, the first patch required at the bottom of the list.')
                      help='Define the path to a single patch. Multiple patches are not yet ' + \
                           'supported.')
    parser.add_option('--enable-pymake', dest='enablePymake', action='store_true',
                      help='Enable pymake. Defaults to "%default" on the current platform.')
    parser.add_option('--enable-threadsafe', dest='enableTs', action='store_true',
                      help='Enable compilation and fuzzing of threadsafe js shell. ' + \
                           'NSPR should first be installed, see: ' + \
                           'https://developer.mozilla.org/en/NSPR_build_instructions ' + \
                           'Defaults to "%default".')
    parser.add_option('--enable-valgrind', dest='enableVg', action='store_true',
                      help='Enable valgrind. ' + \
                           'compareJIT will then be disabled due to speed issues. ' + \
                           'Defaults to "%default".')

    # FIXME: This needs to be ripped out in favour of setting it as a boolean and using repoName and
    # compileType instead.
    parser.add_option('-u', '--use-tinderboxjsshell', dest='useJsShell',
                      help='Specify the tinderbox URL to download instead of compiling ' + \
                           'the js shell. Defaults to "latest" to get the most updated ' + \
                           'tinderbox version.')

    options, args = parser.parse_args()
    return options

def baseDir():
    '''
    Returns different base directories depending on whether system is a VM or not.
    '''
    if isVM() == ('Windows', True):
        return os.path.join('z:', os.sep)
    elif isVM() == ('Linux', True):
        return os.path.join('/', 'mnt', 'hgfs')
    else:
        return '~'

def getRepoNameInHgrc(rDir):
    '''
    Checks to see if the input repository is supported.
    '''
    assert os.path.exists(rDir)
    hgrcFile = normExpUserPath(os.path.join(rDir, '.hg', 'hgrc'))
    assert os.path.isfile(hgrcFile)

    hgCfg = SafeConfigParser()
    hgCfg.read(hgrcFile)
    # Not all default entries in [paths] end with "/".
    rName = filter(None, (hgCfg.get('paths', 'default').split('/')))[-1]
    vdump('Repository name is: ' + rName)
    return rName

def mkFullPath(hgHash, hgNum, pDir, repo, start):
    '''
    Creates the fuzzing directory in the start path.
    '''
    appendStr = '-' + hgHash + '-' + hgNum
    if pDir is not None:
        appendStr += '-patched'
    path = mkdtemp(appendStr + os.sep,
                       os.path.join('jsfunfuzz-' + repo + '-'), start)
    assert os.path.exists(path)
    return path

def copyJsSrcDirs(fPath, repo):
    '''
    Copies required js source directories into the specified path.
    '''
    cPath = normExpUserPath(os.path.join(fPath, 'compilePath', 'js', 'src'))
    origJsSrc = normExpUserPath(os.path.join(repo, 'js', 'src'))
    try:
        vdump('Copying the js source tree, which is located at ' + origJsSrc)
        if sys.version_info >= (2, 6):
            shutil.copytree(origJsSrc, cPath,
                            ignore=shutil.ignore_patterns(
                                'jit-test', 'tests', 'trace-test', 'xpconnect'))
        else:
            shutil.copytree(origJsSrc, cPath)  # Remove once Python 2.5.x is no longer used.
        vdump('Finished copying the js tree')
    except OSError:
        raise Exception('Do the js source directory or the destination exist?')

    # 91a8d742c509 introduced a mfbt directory on the same level as the js/ directory.
    mfbtDir = normExpUserPath(os.path.join(repo, 'mfbt'))
    if os.path.isdir(mfbtDir):
        shutil.copytree(mfbtDir, os.path.join(cPath, os.pardir, os.pardir, 'mfbt'))

    # b9c673621e1e introduced a public directory on the same level as the js/src directory.
    jsPubDir = normExpUserPath(os.path.join(repo, 'js', 'public'))
    if os.path.isdir(jsPubDir):
        shutil.copytree(jsPubDir, os.path.join(cPath, os.pardir, 'public'))

    return cPath

def cfgCompileCopy(cPath, aNum, cType, threadsafety, rName, setPymake, src, fPath, setValg):
    '''
    Configures, compiles then copies a js shell, according to its parameters, and returns its name.
    '''
    cfgPath = normExpUserPath(os.path.join(cPath, 'configure'))
    autoconfRun(cPath)
    objdir = os.path.join(cPath, cType + '-objdir')
    try:
        os.mkdir(objdir)
    except OSError:
        raise Exception('Unable to create objdir.')
    try:
        output, envVarList, cfgEnvDt, cfgCmdList = cfgJsBin(aNum, cType, threadsafety, cfgPath, objdir)
    except Exception, e:
        if platform.system() == 'Windows':
            print 'Temporary debug: configuration failed!'
            pdb.set_trace()
        if platform.system() == 'Windows' and 'Permission denied' in repr(e):
            print 'Trying once more because of "Permission denied" error...'
            output, envVarList, cfgEnvDt, cfgCmdList = cfgJsBin(aNum, cType, threadsafety, cfgPath,
                                                                objdir)
        else:
            print repr(e)
            raise Exception('Configuration of the js binary failed.')
    sname = compileCopy(aNum, cType, rName, setPymake, src, fPath, objdir, setValg)
    assert sname != ''
    return sname, envVarList, cfgEnvDt, cfgCmdList

def knownBugsDir(srcRepo, repoName):
    '''
    Defines the known bugs' directory and returns it as a string.
    '''
    # Define the corresponding known-bugs directories.
    global path0
    mcKnDir = os.path.abspath(os.path.join(path0, os.pardir, 'known', 'mozilla-central'))
    if repoName == 'ionmonkey':
        return normExpUserPath(os.path.join(mcKnDir, 'ionmonkey'))
    elif repoName == 'mozilla-esr10':
        return os.path.abspath(
            normExpUserPath(os.path.join(path0, os.pardir, 'known', 'mozilla-esr10')))
    elif repoName != 'mozilla-central':
        # XXX: mozilla-aurora, mozilla-beta and mozilla-release directories should have their
        # own "known" directories. Using mozilla-central for now.
        vdump('Ignore list for the ' + repoName + ' repository does not exist, so using the ' + \
              'ignore list for mozilla-central.')
    return mcKnDir

def genJsCliFlagList(noCompareJIT, noRndFlags, enableDbg, setV, shFlags, srcRepo, repoName):
    '''
    Returns a list of CLI flags for the js shell.
    '''
    loopFList = []
    loopFList.append('--repo=' + srcRepo)
    if setV:
        loopFList.append('--valgrind')
    if not noCompareJIT:
        loopFList.append('--comparejit')

    if not noRndFlags:
        loopFList.append('--random-flags')
    elif enableDbg:
        shFlags.append('-d')

    return loopFList, shFlags

def genShellCmd(lfList, lTimeout, repoKnDir, shName, shFlags):
    '''
    Returns a list of the shell command to be run.
    '''
    shCmdList = []
    # Define fuzzing command with the required parameters.
    shCmdList.append('python')
    shCmdList.append('-u')
    global path0
    shCmdList.append(os.path.abspath(os.path.join(path0, 'loopjsfunfuzz.py')))
    shCmdList.extend(lfList)
    shCmdList.append(lTimeout)
    shCmdList.append(repoKnDir)
    shCmdList.append(shName)
    shCmdList.extend(shFlags)

    return shCmdList

def selfTests(shName, aNum, cType):
    '''
    Runs a bunch of verification tests to see if arch and compile type are as intended.
    '''
    assert archOfBinary(shName) == aNum  # 32-bit or 64-bit verification test.
    assert testDbgOrOpt(shName) == cType

def outputStrFromList(lst):
    '''
    Escapes backslashes in Windows, for commands that can then be copied and pasted into the shell.
    For all platforms, returns a string form with a space joining each element in the list.
    '''
    return ' '.join(lst).replace('\\', '\\\\') if platform.system() == 'Windows' else ' '.join(lst)

def diagDump(fPath, cmdStr, aNum, cType, rName, eVarList, fEnvDt, cCmdList):
    '''
    Dumps commands to file and also prints them to stdout prior to fuzzing, for reference.
    '''
    localLog = normExpUserPath(os.path.join(fPath, 'log-localjsfunfuzz.txt'))
    with open(localLog, 'wb') as f:
        f.writelines('Environment variables added are:\n')
        f.writelines(' '.join(eVarList) + '\n')
        f.writelines('Full environment is: ' + str(fEnvDt) + '\n')
        f.writelines('Configuration command was:\n')
        f.writelines(' '.join(cCmdList) + '\n')
        f.writelines('Command to be run is:\n')
        f.writelines(cmdStr + '\n')
        f.writelines('========================================================\n')
        f.writelines('|  Fuzzing %s %s %s js shell builds\n' % (aNum + '-bit', cType, rName ))
        f.writelines('|  DATE: %s\n' % dateStr())
        f.writelines('========================================================\n')

    with open(localLog, 'rb') as f:
        for line in f:
            if 'Full environment is' not in line:
                print line,

def defaultStartDir():
    '''
    Set a different default starting directory if machine is a virtual machine.
    '''
    if isVM() == ('Windows', True):
        # FIXME: Add an assertion that isVM() is a WinXP VM, and not Vista/Win7/Win8.
        # Set to root directory of Windows VM since we only test WinXP in a VM.
        # This might fail on a Vista or Win7 VM due to lack of permissions.
        # FIXME: Maybe a directory can be passed in? Or why not always use the Desktop?
        # It would be good to get this machine-specific hack out of the shared file, eventually.
        sDir = os.path.join('c:', os.sep)
    else:
        sDir = normExpUserPath(os.path.join('~', 'Desktop'))
    return sDir

def getAnalysisFiles(path):
    '''
    Copy over useful files that are updated in hg fuzzing branch.
    '''
    global path0
    if os.path.exists(os.path.abspath(os.path.join(path0, os.pardir, 'jsfunfuzz', 'analysis.py'))):
        shutil.copy2(os.path.abspath(
            os.path.join(path0, os.pardir, 'jsfunfuzz', 'analysis.py')), path)

def setFlags(options):
    '''
    Sets the default flags.
    '''
    fList = filter(None, options.shellflags.split(','))
    assert options.disableCompareJIT or '-D' not in fList  # -D outputs a lot of spew.
    if fList == []:
        fList = ['-m', '-a', '-n']
    else:
        # If flags are specified, --disable-random-flags should be specified.
        assert options.disableRndFlags
    return fList

def localCompileFuzzJsShell(options):
    '''
    Compiles and readies a js shell for fuzzing.
    '''
    patchDir = normExpUserPath(options.patchdir) if options.patchdir is not None else None

    archList = options.archType.split(',')
    assert '32' in archList or '64' in archList
    # 32-bit and 64-bit cannot be fuzzed together in the same MozillaBuild batch script in Windows.
    assert not ('32' in archList and '64' in archList), '32 & 64-bit cannot be fuzzed together yet.'
    if platform.system() == 'Windows':
        assert 'x64' in os.environ['MOZ_TOOLS'].split(os.sep)[-1] or options.archType == '32'
        assert 'x64' not in os.environ['MOZ_TOOLS'].split(os.sep)[-1] or options.archType == '64'
    shellTypeList = options.shellType.split(',')
    assert 'dbg' in shellTypeList or 'opt' in shellTypeList

    shFlagList = setFlags(options)

    # Set different timeouts depending on machine.
    loopyTimeout = str(machineTypeDefaults(options.timeout))
    if options.enableVg:
        if (platform.system() == 'Linux' or platform.system() == 'Darwin') \
            and platform.uname()[4] != 'armv7l':
            loopyTimeout = '300'
        else:
            raise Exception('Valgrind is only supported on Linux or Mac OS X machines.')

    print dateStr()
    srcRepo = normExpUserPath(options.srcRepo)
    repoName = getRepoNameInHgrc(srcRepo)

    localOrigHgHash, localOrigHgNum, isOnDefault = getRepoHashAndId(srcRepo)

    setPymake = options.enablePymake
    if setPymake and not isOnDefault:
        vdump('We are not on default, so turning off pymake now.')
        setPymake = False  # Turn off pymake if not on default tip.

    intendedDir = defaultStartDir()

    # Assumes that all patches that need to be applied will be done through --enable-patch-dir=FOO.
    assert captureStdout(['hg', 'qapp'], currWorkingDir=srcRepo)[0] == ''

    if patchDir is not None:
        # Assumes mq extension is enabled in Mercurial config.
        # Series file should be optional if only one patch is needed.
        assert not os.path.isdir(patchDir), 'Support for multiple patches has not yet been added.'
        if os.path.isfile(patchDir):
            p1name = patchHgRepoUsingMq(patchDir, srcRepo)

    fullPath = mkFullPath(localOrigHgHash, localOrigHgNum, patchDir, repoName, intendedDir)

    # Copy js src dirs to compilePath, to have a backup of shell source in case repo gets updated.
    compilePath = copyJsSrcDirs(fullPath, srcRepo)

    if patchDir is not None:
        # Remove the patches from the codebase if they were applied.
        assert not os.path.isdir(patchDir), 'Support for multiple patches has not yet been added.'
        assert p1name != ''
        if os.path.isfile(patchDir):
            subprocess.check_call(['hg', 'qpop'], cwd=srcRepo)
            vdump("First patch qpop'ed.")
            subprocess.check_call(['hg', 'qdelete', p1name], cwd=srcRepo)
            vdump("First patch qdelete'd.")

    # Ensure there is no applied patch remaining in the main repository.
    assert captureStdout(['hg', 'qapp'], currWorkingDir=srcRepo)[0] == ''

    vdump('archList is: ' + str(archList))
    # FIXME: Change this once target time is implemented in loopjsfunfuzz.py
    # Default to compiling 32-bit first, unless 32-bit builds are specifically not to be built.
    archNum = '32' if '32' in archList else '64'

    vdump('shellTypeList is: ' + str(shellTypeList))
    # Default to compiling debug first, unless debug builds are specifically not to be built.
    shellType = 'dbg' if 'dbg' in shellTypeList else 'opt'

    shellName, addedEnvList, fullEnvDt, configCmdList = cfgCompileCopy(compilePath, archNum,
        shellType, options.enableTs, repoName, setPymake, srcRepo, fullPath, options.enableVg)

    # FIXME: Change this once target time is implemented in loopjsfunfuzz.py
    # Always compile the other same-arch shell for future testing purposes.
    shellType2 = 'opt' if shellType == 'dbg' else 'dbg'
    cfgCompileCopy(compilePath, archNum, shellType2, options.enableTs, repoName, setPymake,
                   srcRepo, fullPath, options.enableVg)

    getAnalysisFiles(fullPath)

    loopFlagList, shFlagList = genJsCliFlagList(
        options.disableCompareJIT, options.disableRndFlags, 'dbg' in shellTypeList,
        options.enableVg, shFlagList, srcRepo, repoName)

    shellCmdList = genShellCmd(
        loopFlagList, loopyTimeout, knownBugsDir(srcRepo, repoName), shellName, shFlagList)

    selfTests(shellName, archNum, shellType)

    diagDump(fullPath, outputStrFromList(shellCmdList), archNum, shellType, repoName, addedEnvList,
             fullEnvDt, configCmdList)

    # FIXME: Randomize logic should be developed later, possibly together with target time in
    # loopjsfunfuzz.py. Randomize Valgrind runs too.

    return shellCmdList, fullPath

def startFuzzing(options, cmdList, path):
    '''
    Start fuzzing if appropriate.
    '''
    if options.disableStartFuzzing:
        print 'Exiting, --disable-start-fuzzing is set.'
        sys.exit(0)

    # Commands to simulate bash's `tee`.
    tee = subprocess.Popen(['tee', 'log-jsfunfuzz.txt'], stdin=subprocess.PIPE, cwd=path)

    # Note that js shells should be compiled with --enable-more-deterministic.
    # Start fuzzing the newly compiled builds.
    subprocess.call(cmdList, stdout=tee.stdin, cwd=path)

class DownloadedJsShell:
    def __init__(self, options):
        if options.shellType == 'dbg,opt' or options.shellType == 'dbg':
            self.cType = 'dbg'  # 'dbg,opt' is the default setting for options.shellType
            if 'dbg' in options.shellType:
                print 'Setting to debug only even though opt is specified by default. ' + \
                      'Overwrite this by specifying the shell type explicitly.'
        elif options.shellType == 'opt':
            self.cType = 'opt'

        if options.archType == '32':
            self.pArchNum = '32'
            if platform.system() == 'Darwin':
                self.pArchName = 'macosx'
            elif platform.system() == 'Linux':
                self.pArchName = 'linux'
            elif platform.system() in ('Microsoft', 'Windows'):
                self.pArchName = 'win32'
        elif options.archType == '64':
            self.pArchNum = '64'
            if platform.system() == 'Darwin':
                self.pArchName = 'macosx64'
            elif platform.system() == 'Linux':
                self.pArchName = 'linux64'
            elif platform.system() in ('Microsoft', 'Windows'):
                raise Exception('Windows 64-bit builds are not supported yet.')
        else:
            raise Exception('Only either one of these architectures can be specified: 32 or 64')
        self.srcRepo = options.srcRepo
        self.repo = self.srcRepo.split('/')[-1]
        self.shellVer = options.useJsShell
    def mkFuzzDir(self, startDir):
        path = mkdtemp('', os.path.join('tinderjsfunfuzz-'), startDir)
        assert os.path.exists(path)
        return path
    def downloadShell(self, sDir):
        remoteTinderJsUrlStart = 'https://ftp.mozilla.org/pub/mozilla.org/firefox/tinderbox-builds/'
        tinderJsType = filter(None, self.repo) + '-' + self.pArchName + \
            '-debug' if 'dbg' in self.cType else ''
        if self.shellVer == 'latest':
            downloadLatestBuild(tinderJsType, getJsShell=True, workingDir=sDir)
        elif remoteTinderJsUrlStart in self.shellVer:
            downloadBuild(self.shellVer, cwd=sDir, jsShell=True, wantSymbols=False)
        else:
            raise Exception('Please specify either "latest" or ' + \
                            'the URL of the tinderbox build to be used.' + \
                            'e.g. FIXME')
        self.shellName = os.path.abspath(normExpUserPath(os.path.join(sDir, 'build', 'dist', 'js')))
        assert os.path.exists(self.shellName)

def main():
    options = parseOptions()

    if options.useJsShell is None:
        cList, startDir = localCompileFuzzJsShell(options)
    else:
        odjs = DownloadedJsShell(options)
        startDir = odjs.mkFuzzDir(defaultStartDir())
        odjs.downloadShell(startDir)

        getAnalysisFiles(startDir)

        shFlagList = setFlags(options)

        loopyTimeout = str(machineTypeDefaults(options.timeout))
        if options.enableVg:
            if (platform.system() == 'Linux' or platform.system() == 'Darwin') \
                and platform.uname()[4] != 'armv7l':
                loopyTimeout = '300'
            else:
                raise Exception('Valgrind is only supported on Linux or Mac OS X machines.')

        loopFlagList, shFlagList = genJsCliFlagList(
            options.disableCompareJIT, options.disableRndFlags, 'dbg' == odjs.cType,
            options.enableVg, shFlagList, odjs.srcRepo, odjs.repo)

        cList = genShellCmd(loopFlagList, loopyTimeout,
                            knownBugsDir(odjs.srcRepo, odjs.repo), odjs.shellName, shFlagList)

        selfTests(odjs.shellName, odjs.pArchNum, odjs.cType)

        localLog = normExpUserPath(os.path.join(startDir, 'log-localjsfunfuzz.txt'))
        with open(localLog, 'wb') as f:
            f.writelines('Command to be run is:\n')
            f.writelines(outputStrFromList(cList) + '\n')
            f.writelines('========================================================\n')
            f.writelines('|  Fuzzing %s %s %s js shell builds\n' % (odjs.pArchNum + '-bit',
                                                                    odjs.cType, odjs.repo ))
            f.writelines('|  DATE: %s\n' % dateStr())
            f.writelines('========================================================\n')

        with open(localLog, 'rb') as f:
            for line in f:
                print line,

    startFuzzing(options, cList, startDir)


# Run main when run as a script, this line means it will not be run as a module.
if __name__ == '__main__':
    main()

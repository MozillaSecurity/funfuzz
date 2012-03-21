#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import platform
import shutil
import subprocess
import sys

from random import randint
from compileShell import hgHashAddToFuzzPath, patchHgRepoUsingMq, autoconfRun, cfgJsBin, compileCopy
from inspectShell import archOfBinary, testDbgOrOptGivenACompileType

path0 = os.path.dirname(__file__)
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
from subprocesses import dateStr, isVM, normExpUserPath, vdump

def main():
    print dateStr()
    mjit = True  # turn on -m
    mjitAll = True  # turn on -a
    debugJit = True  # turn on -d
    codeProfiling = False  # turn on -D
    usePymake = True if platform.system() == 'Windows' else False
    jsCompareJITSwitch = True if mjit else False
    # Sets --enable-threadsafe for a multithreaded js shell, first make sure NSPR is installed!
    # (Use `make` instead of `gmake`), see https://developer.mozilla.org/en/NSPR_build_instructions
    threadsafe = False

    if platform.uname()[1] == 'tegra-ubuntu':
        mTimedRunTimeout = '180'
    elif platform.uname()[4] == 'armv7l':
        mTimedRunTimeout = '600'
    else:
        mTimedRunTimeout = '10'

    vgBool = False
    if platform.system() == 'Linux' or platform.system() == 'Darwin':
        if (len(sys.argv) == 5 and sys.argv[4] == 'valgrind') or \
            (len(sys.argv) == 7 and sys.argv[6] == 'valgrind') or \
            (len(sys.argv) == 9 and sys.argv[8] == 'valgrind') or \
            (len(sys.argv) == 11 and sys.argv[10] == 'valgrind'):
            # Valgrind does not work for 32-bit binaries in a 64-bit Linux system.
            if platform.system() == 'Linux':
                assert platform.uname()[4] == 'x86_64' and sys.argv[1] == '64'
            vgBool = True
            jsCompareJITSwitch = False  # Turn off compareJIT (too slow) when in Valgrind.
            mTimedRunTimeout = '300'  # Increase timeout to 300 in Valgrind.

    if platform.system() == "Linux" or platform.system() == "Darwin":
        vdump('Setting ulimit -c to unlimited..')
        # ulimit requires shell=True to work properly.
        subprocess.check_call(['ulimit -S -c unlimited'], shell=True) # Enable creation of coredumps
        if platform.system() == "Linux":
            # Only allow one process to create a coredump at a time.
            p1 = subprocess.Popen(
                ['echo', '1'], stdout=subprocess.PIPE)
            p2 = subprocess.Popen(
                ['sudo tee /proc/sys/kernel/core_uses_pid'], stdin=p1.stdout,
                    stdout=subprocess.PIPE, shell=True)
            p1.stdout.close()
            (p2stdout, p2stderr) = p2.communicate()[0]
            vdump(p2stdout)
            vdump(p2stderr)
            try:
                fcoreuses = open('/proc/sys/kernel/core_uses_pid', 'r')
            except IOError:
                raise
            assert '1' in fcoreuses.readline() # Double-check that only one process is allowed
            fcoreuses.close()

    if sys.argv[3] == '192':
        jsCompareJITSwitch = False

    if codeProfiling == True:
        # -D intentionally outputs a lot of console spew.
        jsCompareJITSwitch = False

    # There should be a minimum of 4 command-line parameters.
    if len(sys.argv) < 4:
        raise Exception('Too little command-line parameters.')

    archNum = sys.argv[1]
    assert int(archNum) in (32, 64)
    compileType = sys.argv[2]
    assert compileType in ('dbg', 'opt')

    branchSuppList = []
    branchSuppList.append('192')
    branchSuppList.append('mc')
    branchSuppList.append('jm')
    branchSuppList.append('im')
    branchSuppList.append('mi')
    branchSuppList.append('larch')
    branchSuppList.append('ma')
    branchSuppList.append('mb')
    branchSuppList.append('esr10')
    branchType = sys.argv[3]
    assert branchType in branchSuppList

    repoDt = {}
    if isVM() == ('Windows', True):
        startVMorNot = os.path.join('z:', os.sep)
    elif isVM() == ('Linux', True):
        startVMorNot = os.path.join('/', 'mnt', 'hgfs')
    else:
        startVMorNot = '~'
    repoDt['fuzzing'] = normExpUserPath(os.path.join(startVMorNot, 'fuzzing'))
    assert os.path.exists(repoDt['fuzzing'])
    repoDt['192'] = normExpUserPath(os.path.join(startVMorNot, 'trees', 'mozilla-1.9.2'))
    repoDt['mc'] = normExpUserPath(os.path.join(startVMorNot, 'trees', 'mozilla-central'))
    repoDt['jm'] = normExpUserPath(os.path.join(startVMorNot, 'trees', 'jaegermonkey'))
    repoDt['im'] = normExpUserPath(os.path.join(startVMorNot, 'trees', 'ionmonkey'))
    repoDt['mi'] = normExpUserPath(os.path.join(startVMorNot, 'trees', 'mozilla-inbound'))
    repoDt['larch'] = normExpUserPath(os.path.join(startVMorNot, 'trees', 'larch'))
    repoDt['ma'] = normExpUserPath(os.path.join(startVMorNot, 'trees', 'mozilla-aurora'))
    repoDt['mb'] = normExpUserPath(os.path.join(startVMorNot, 'trees', 'mozilla-beta'))
    repoDt['esr10'] = normExpUserPath(os.path.join(startVMorNot, 'trees', 'mozilla-esr10'))

    for repo in repoDt.keys():
        vdump('The "' + repo + '" repository is located at "' + repoDt[repo] + '"')

    fuzzPathStart = os.path.join('c:', os.sep) if isVM() == ('Windows', True) \
        else os.path.join('~', 'Desktop')
    fuzzPath = normExpUserPath(
        os.path.join(
            fuzzPathStart, 'jsfunfuzz-' + compileType + '-' + archNum + '-' + branchType)
        )

    # Patch the codebase if specified, accept up to 3 patches.
    if len(sys.argv) >= 6 and sys.argv[4] == 'patch':
        print 'NOTE: The hash in the directory is post-patch, not pre-patch!'
        p1name = patchHgRepoUsingMq(sys.argv[5], repoDt[branchType])
        if len(sys.argv) >= 8 and sys.argv[6] == 'patch':
            p2name = patchHgRepoUsingMq(sys.argv[7], repoDt[branchType])
            if len(sys.argv) >= 10 and sys.argv[8] == 'patch':
                p3name = patchHgRepoUsingMq(sys.argv[9], repoDt[branchType])

    # Patches must already been qimport'ed and qpush'ed.
    # FIXME: we should grab the hash first before applying the patch
    (fuzzPath, onDefaultTip) = hgHashAddToFuzzPath(fuzzPath, repoDt[branchType])

    # Turn off pymake if not on default tip.
    if usePymake and not onDefaultTip:
        usePymake = False

    compilePath = normExpUserPath(os.path.join(fuzzPath, 'compilePath', 'js', 'src'))
    # Copy the js tree to the fuzzPath.
    jsSrcDir = normExpUserPath(os.path.join(repoDt[branchType], 'js', 'src'))
    try:
        vdump('Copying the js source tree, which is located at ' + jsSrcDir)
        if sys.version_info >= (2, 6):
            shutil.copytree(jsSrcDir, compilePath,
                            ignore=shutil.ignore_patterns(
                                'jit-test', 'tests', 'trace-test', 'xpconnect'))
        else:
            shutil.copytree(jsSrcDir, compilePath)
        vdump('Finished copying the js tree')
    except OSError:
        raise Exception('Do the js source directory or the destination exist?')

    # 91a8d742c509 introduced a mfbt directory on the same level as the js/ directory.
    mfbtDir = normExpUserPath(os.path.join(repoDt[branchType], 'mfbt'))
    if os.path.isdir(mfbtDir):
        shutil.copytree(mfbtDir, os.path.join(compilePath, '..', '..', 'mfbt'))

    # b9c673621e1e introduced a public directory on the same level as the js/src directory.
    jsPubDir = normExpUserPath(os.path.join(repoDt[branchType], 'js', 'public'))
    if os.path.isdir(jsPubDir):
        shutil.copytree(jsPubDir, os.path.join(compilePath, '..', 'public'))

    # Remove the patches from the codebase if they were applied
    if len(sys.argv) >= 6 and sys.argv[4] == 'patch':
        subprocess.check_call(['hg', 'qpop'], cwd=repoDt[branchType])
        vdump("First patch qpop'ed.")
        subprocess.check_call(['hg', 'qdelete', p1name], cwd=repoDt[branchType])
        vdump("First patch qdelete'd.")
        if len(sys.argv) >= 8 and sys.argv[6] == 'patch':
            subprocess.check_call(['hg', 'qpop'], cwd=repoDt[branchType])
            vdump("Second patch qpop'ed.")
            subprocess.check_call(['hg', 'qdelete', p2name], cwd=repoDt[branchType])
            vdump("Second patch qdelete'd.")
            if len(sys.argv) >= 10 and sys.argv[8] == 'patch':
                subprocess.check_call(['hg', 'qpop'], cwd=repoDt[branchType])
                vdump("Third patch qpop'ed.")
                subprocess.check_call(['hg', 'qdelete', p3name], cwd=repoDt[branchType])
                vdump("Third patch qdelete'd.")

    autoconfRun(compilePath)

    cfgPath = normExpUserPath(os.path.join(compilePath, 'configure'))
    # Compile the first binary.
    objdir = os.path.join(compilePath, compileType + '-objdir')
    os.mkdir(objdir)
    cfgJsBin(archNum, compileType, threadsafe, cfgPath, objdir)
    shname = compileCopy(archNum, compileType, branchType, usePymake, repoDt[branchType],
                         fuzzPath, objdir, vgBool)

    # Re-run autoconf again.
    autoconfRun(compilePath)

    # Compile the other shell.
    if compileType == 'dbg':
        objdir2 = os.path.join(compilePath, 'opt-objdir')
    elif compileType == 'opt':
        objdir2 = os.path.join(compilePath, 'dbg-objdir')
    os.mkdir(objdir2)

    # No need to assign shname here, because we are not fuzzing this one.
    if compileType == 'dbg':
        cfgJsBin(archNum, 'opt', threadsafe, cfgPath, objdir2)
        compileCopy(archNum, 'opt', branchType, usePymake, repoDt[branchType], fuzzPath, objdir2,
                    vgBool)
    elif compileType == 'opt':
        cfgJsBin(archNum, 'dbg', threadsafe, cfgPath, objdir2)
        compileCopy(archNum, 'dbg', branchType, usePymake, repoDt[branchType], fuzzPath, objdir2,
                    vgBool)

    # Copy over useful files that are updated in hg fuzzing branch.
    shutil.copy2(
        normExpUserPath(os.path.join(repoDt['fuzzing'], 'jsfunfuzz', 'analysis.py')), fuzzPath)
    shutil.copy2(
        normExpUserPath(
            os.path.join(repoDt['fuzzing'], 'jsfunfuzz', 'runFindInterestingFiles.py')), fuzzPath)

    jsknwnDt = {}
    # Define the corresponding js-known directories.
    jsknwnDt['192'] = normExpUserPath(os.path.join(repoDt['fuzzing'], 'js-known', 'mozilla-1.9.2'))
    jsknwnDt['mc'] = normExpUserPath(os.path.join(repoDt['fuzzing'], 'js-known', 'mozilla-central'))
    jsknwnDt['jm'] = jsknwnDt['mc']
    jsknwnDt['im'] = jsknwnDt['mc']
    jsknwnDt['mi'] = jsknwnDt['mc']
    jsknwnDt['larch'] = jsknwnDt['mc']
    jsknwnDt['ma'] = jsknwnDt['mc']
    jsknwnDt['mb'] = jsknwnDt['mc']
    jsknwnDt['esr10'] = jsknwnDt['mc']

    mTimedRunFlagList = []
    mTimedRunFlagList.append('--random-flags')
    if jsCompareJITSwitch:
        mTimedRunFlagList.append('--comparejit')
    if vgBool:
        mTimedRunFlagList.append('--valgrind')
    if branchType == 'mc':
        mTimedRunFlagList.append('--repo=' + repoDt['mc'])
    elif branchType == 'jm':
        mTimedRunFlagList.append('--repo=' + repoDt['jm'])
    elif branchType == 'im':
        mTimedRunFlagList.append('--repo=' + repoDt['im'])
    elif branchType == 'mi':
        mTimedRunFlagList.append('--repo=' + repoDt['mi'])
    elif branchType == 'larch':
        mTimedRunFlagList.append('--repo=' + repoDt['larch'])
    elif branchType == 'ma':
        mTimedRunFlagList.append('--repo=' + repoDt['ma'])
    elif branchType == 'mb':
        mTimedRunFlagList.append('--repo=' + repoDt['mb'])
    elif branchType == 'esr10':
        mTimedRunFlagList.append('--repo=' + repoDt['esr10'])

    jsCliFlagList = []
    if mjit:
        jsCliFlagList.append('-m')
        jsCliFlagList.append('-n')
        if mjitAll:
            jsCliFlagList.append('-a')
    if debugJit:
        jsCliFlagList.append('-d')
    if codeProfiling:
        jsCliFlagList.append('-D')
    # Thanks to decoder and sstangl, useful flag combinations are:
    # {{--ion -n, --ion, --ion-eager} x {--ion-regalloc=greedy, --ion-regalloc=lsra}}
    if branchType == 'im':
        #rndIntIM = randint(0, 5)  # randint comes from the random module.
        # --random-flags takes in flags from jsInteresting.py, so it must be disabled.
        mTimedRunFlagList.remove('--random-flags')
        if '-d' in jsCliFlagList:
            jsCliFlagList.remove('-d')  # as of early Feb 2012, -d disables --ion
        if '-n' in jsCliFlagList:
            jsCliFlagList.remove('-n')
        assert '--random-flags' not in mTimedRunFlagList
        jsCliFlagList.append('--ion')
        jsCliFlagList.append('-n')  # ensure -n is really appended.
        #jsCliFlagList.append('--ion-eager')

        # Description from bug 724444:
        #We're ready for fuzzing! (I hope.)
        #
        #To run IonMonkey, you need --ion -n. Running --ion without -n isn't supported.
        #
        #Other interesting flags:
        #    --ion-eager:    Compile eagerly, like -a. This is somewhat buggy right now.
        #    --ion-gvn=off:  Disables folding/code elimination.
        #    --ion-licm=off: Disables loop hoisting.
        #    --ion-inlining=off: Disables function inlining.
        #    -m: Still enables the method JIT,
        #
        #There are other --ion flags but they are experimental and not ready for testing. Also note, -a has no effect on --ion and -d will disable ion.

    fuzzCmdList = []
    # Define fuzzing command with the required parameters.
    fuzzCmdList.append('python')
    fuzzCmdList.append('-u')
    mTimedRun = normExpUserPath(os.path.join(repoDt['fuzzing'], 'js', 'loopjsfunfuzz.py'))
    fuzzCmdList.append(mTimedRun)
    fuzzCmdList.extend(mTimedRunFlagList)
    fuzzCmdList.append(mTimedRunTimeout)
    fuzzCmdList.append(jsknwnDt[branchType])
    fuzzCmdList.append(shname)
    fuzzCmdList.extend(jsCliFlagList)

    if platform.system() == 'Windows':
        print('fuzzCmd is: ' + ' '.join(fuzzCmdList).replace('\\', '\\\\') + '\n')
    else:
        print('fuzzCmd is: ' + ' '.join(fuzzCmdList) + '\n')

    if platform.system() == 'Linux' or platform.system() == 'Darwin':
        assert archOfBinary(shname) == archNum  # 32-bit or 64-bit verification test.
    if sys.version_info >= (2, 6):
        # The following line doesn't seem to work in Python 2.5 because of NamedTemporaryFile
        testDbgOrOptGivenACompileType(shname, compileType, cwd=fuzzPath)

    print '''
    ================================================
    !  Fuzzing %s %s %s js shell builds now  !
       DATE: %s
    ================================================
    ''' % (archNum + '-bit', compileType, branchType, dateStr() )

    # Commands to simulate bash's `tee`.
    tee = subprocess.Popen(['tee', 'log-jsfunfuzz'], stdin=subprocess.PIPE, cwd=fuzzPath)

    # Start fuzzing the newly compiled builds.
    subprocess.call(fuzzCmdList, stdout=tee.stdin, cwd=fuzzPath)

# Run main when run as a script, this line means it will not be run as a module.
if __name__ == '__main__':
    main()

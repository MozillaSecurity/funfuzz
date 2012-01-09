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
import time

from random import randint
from fnStartjsfunfuzz import vdump, normExpUserPath, bashDate, hgHashAddToFuzzPath, \
    patchHgRepoUsingMq, autoconfRun, cfgJsBin, compileCopy, archOfBinary, \
    testDbgOrOptGivenACompileType

def main():
    print bashDate()
    mjit = True  # turn on -m
    mjitAll = True  # turn on -a
    debugJit = True  # turn on -d
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
            vgBool = True
            jsCompareJITSwitch = False  # Turn off compareJIT (too slow) when in Valgrind.
            mTimedRunTimeout = '300'  # Increase timeout to 300 in Valgrind.

    if platform.system() == "Linux" or platform.system() == "Darwin":
        vdump('Setting ulimit -c to unlimited..')
        subprocess.check_call(['ulimit', '-c', 'unlimited']) # Enable creation of coredumps.
        if platform.system() == "Linux":
            fnull = open(os.devnull, 'w')
            # Only allow one process to create a coredump at a time.
            p1 = subprocess.Popen(
                ['echo', '1'], stdout=subprocess.PIPE)
            p2 = subprocess.Popen(
                ['sudo', 'tee', '/proc/sys/kernel/core_uses_pid'], stdin=p1.stdout, stdout=fnull)
            p1.stdout.close()
            (p2stdout, p2stderr) = p2.communicate()[0]  # p2stdout should have been piped to null
            fnull.close()
            vdump(p2stdout)
            vdump(p2stderr)
            try:
                fcoreuses = open('/proc/sys/kernel/core_uses_pid', 'r')
            except IOError as e:
                raise
            assert '1' in fcoreuses.readline() # Double-check that only one process is allowed
            fcoreuses.close()

            if sys.argv[1] == '64':
                # 64-bit js shells have only been tested on Linux x86_64 (AMD64) platforms.
                assert platform.system() == 'Linux' and platform.uname()[4] == 'x86_64'

    if sys.argv[3] == '192':
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
    branchType = sys.argv[3]
    assert branchType in branchSuppList

    repoDt = {}
    repoDt['fuzzing'] = normExpUserPath(os.path.join('~', 'fuzzing'))
    repoDt['192'] = normExpUserPath(os.path.join('~', 'trees', 'mozilla-1.9.2'))
    repoDt['mc'] = normExpUserPath(os.path.join('~', 'trees', 'mozilla-central'))
    repoDt['jm'] = normExpUserPath(os.path.join('~', 'trees', 'jaegermonkey'))
    repoDt['im'] = normExpUserPath(os.path.join('~', 'trees', 'ionmonkey'))
    repoDt['mi'] = normExpUserPath(os.path.join('~', 'trees', 'mozilla-inbound'))
    repoDt['larch'] = normExpUserPath(os.path.join('~', 'trees', 'larch'))
    # for repo in repoDt.keys():
        ## It is assumed that on WinXP, the corresponding directories are in the root / folder.
        # repoDt[repo] = repoDt[repo][1:]
    # fuzzPathStart = '/jsfunfuzz-'  # Start of fuzzing directory

    for repo in repoDt.keys():
        vdump('The "' + repo + '" repository is located at "' + repoDt[repo] + '"')

    fuzzPath = normExpUserPath(
        os.path.join(
            '~', 'Desktop', 'jsfunfuzz-' + compileType + '-' + archNum + '-' + branchType)
        )

    # Patch the codebase if specified, accept up to 3 patches.
    if len(sys.argv) >= 6 and sys.argv[4] == 'patch':
        p1name = patchHgRepoUsingMq(sys.argv[5], repoDt[branchType])
        if len(sys.argv) >= 8 and sys.argv[6] == 'patch':
            p2name = patchHgRepoUsingMq(sys.argv[7], repoDt[branchType])
            if len(sys.argv) >= 10 and sys.argv[8] == 'patch':
                p3name = patchHgRepoUsingMq(sys.argv[9], repoDt[branchType])

    # Patches must already been qimport'ed and qpush'ed.
    (fuzzPath, onDefaultTip) = hgHashAddToFuzzPath(fuzzPath, repoDt[branchType])

    # Turn off pymake if not on default tip.
    if usePymake and not onDefaultTip:
        usePymake = False

    compilePath = normExpUserPath(os.path.join(fuzzPath, 'compilePath', 'js', 'src'))
    # Copy the js tree to the fuzzPath.
    jsSrcDir = normExpUserPath(os.path.join(repoDt[branchType], 'js', 'src'))
    try:
        vdump('Copying the js source tree, which is located at ' + jsSrcDir)
        shutil.copytree(jsSrcDir, compilePath,
                        ignore=shutil.ignore_patterns('tests', 'trace-test', 'xpconnect'))
        vdump('Finished copying the js tree')
    except OSError as e:
        vdump(repr(e))
        raise Exception('Do the js source directory or the destination exist?')

    # 91a8d742c509 introduced a mfbt directory on the same level as the js/ directory.
    mfbtDir = normExpUserPath(os.path.join(repoDt[branchType], 'mfbt'))
    if os.path.isdir(mfbtDir):
        shutil.copytree(mfbtDir, os.path.join(compilePath, '..', '..', 'mfbt'),
                        ignore=shutil.ignore_patterns('tests', 'trace-test', 'xpconnect'))

    # b9c673621e1e introduced a public directory on the same level as the js/src directory.
    jsPubDir = normExpUserPath(os.path.join(repoDt[branchType], 'js', 'public'))
    if os.path.isdir(jsPubDir):
        shutil.copytree(jsPubDir, os.path.join(compilePath, '..', 'public'),
                        ignore=shutil.ignore_patterns('tests', 'trace-test', 'xpconnect'))

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
        normExpUserPath(os.path.join(repoDt['fuzzing'], 'jsfunfuzz', 'jsfunfuzz.js')), fuzzPath)
    shutil.copy2(
        normExpUserPath(os.path.join(repoDt['fuzzing'], 'jsfunfuzz', 'analysis.py')), fuzzPath)
    shutil.copy2(
        normExpUserPath(
            os.path.join(repoDt['fuzzing'], 'jsfunfuzz', 'runFindInterestingFiles.py')), fuzzPath)
    shutil.copy2(
        normExpUserPath(os.path.join(repoDt['fuzzing'], 'jsfunfuzz', '4test.py')), fuzzPath)

    jsknwnDt = {}
    # Define the corresponding js-known directories.
    jsknwnDt['192'] = normExpUserPath(os.path.join(repoDt['fuzzing'], 'js-known', 'mozilla-1.9.2'))
    jsknwnDt['mc'] = normExpUserPath(os.path.join(repoDt['fuzzing'], 'js-known', 'mozilla-central'))
    jsknwnDt['jm'] = jsknwnDt['mc']
    jsknwnDt['im'] = jsknwnDt['mc']
    jsknwnDt['mi'] = jsknwnDt['mc']
    jsknwnDt['larch'] = jsknwnDt['mc']

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

    jsCliFlagList = []
    if mjit:
        jsCliFlagList.append('-m')
        jsCliFlagList.append('-n')
        if mjitAll:
            jsCliFlagList.append('-a')
    if debugJit and branchType != 'im':
        jsCliFlagList.append('-d')
    # Thanks to decoder and sstangl, useful flag combinations are:
    # {{--ion -n, --ion, --ion-eager} x {--ion-regalloc=greedy, --ion-regalloc=lsra}}
    if branchType == 'im':
        rndIntIM = randint(0, 5)  # randint comes from the random module.
        # --random-flags takes in flags from jsunhappy, so it must be disabled.
        mTimedRunFlagList.remove('--random-flags')
        assert '--random-flags' not in mTimedRunFlagList
        if rndIntIM == 0:
            jsCliFlagList.append('--ion')
            jsCliFlagList.append('-n')
            jsCliFlagList.append('--ion-regalloc=greedy')
        elif rndIntIM == 1:
            jsCliFlagList.append('--ion')
            jsCliFlagList.append('--ion-regalloc=greedy')
        elif rndIntIM == 2:
            jsCliFlagList.append('--ion-eager')
            jsCliFlagList.append('--ion-regalloc=greedy')
        elif rndIntIM == 3:
            jsCliFlagList.append('--ion')
            jsCliFlagList.append('-n')
            jsCliFlagList.append('--ion-regalloc=lsra')
        elif rndIntIM == 4:
            jsCliFlagList.append('--ion')
            jsCliFlagList.append('--ion-regalloc=lsra')
        elif rndIntIM == 5:
            jsCliFlagList.append('--ion-eager')
            jsCliFlagList.append('--ion-regalloc=lsra')

    fuzzCmdList = []
    # Define fuzzing command with the required parameters.
    fuzzCmdList.append('python')
    fuzzCmdList.append('-u')
    mTimedRun = normExpUserPath(os.path.join(repoDt['fuzzing'], 'jsfunfuzz', 'multi_timed_run.py'))
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
    testDbgOrOptGivenACompileType(shname, compileType)

    print '''
    ================================================
    !  Fuzzing %s %s %s js shell builds now  !
       DATE: %s
    ================================================
    ''' % (archNum + '-bit', compileType, branchType, bashDate() )

    # Commands to simulate bash's `tee`.
    tee = subprocess.Popen(['tee', 'log-jsfunfuzz'], stdin=subprocess.PIPE, cwd=fuzzPath)

    # Start fuzzing the newly compiled builds.
    subprocess.call(fuzzCmdList, stdout=tee.stdin, cwd=fuzzPath)

# Run main when run as a script, this line means it will not be run as a module.
if __name__ == '__main__':
    main()

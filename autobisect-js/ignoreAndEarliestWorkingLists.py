#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import sys

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
from subprocesses import captureStdout, isLinux, isMac, isWin, macVer

def ignoreChangesets(hgPrefix, sourceDir):
    '''Ignores specified changesets that are known to be broken, during hg bisection.'''
    # Reset `hg bisect`
    captureStdout(hgPrefix + ['bisect', '-r'])

    # Skip some busted revisions. It might make sense to avoid (or note) these in checkBlameParents.
    # All numbers in the range excluding boundaries should be broken for some reason.
    # To add to the list, 404.js does not need to exist, WORKINGREV can be default / tip:
    # - (1) will tell you when the brokenness started
    # - (1) autoBisect.py --compilation-failed-label=bad -p -a32 -s WORKINGREV -e FAILINGREV 404.js
    # - (2) will tell you when the brokenness ended
    # - (2) autoBisect.py --compilation-failed-label=bad -p -a32 -s FAILINGREV -e WORKINGREV 404.js
    # Explanation: (descendants(last good changeset)-descendants(first working changeset))
    # Paste numbers into: http://hg.mozilla.org/mozilla-central/rev/<number> to get hgweb link.
    captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(ae22e27106b3)-descendants(785e4e86798b))'], ignoreStderr=True, ignoreExitCode=True) # m-c 100867 - 101115: build breakage involving --enable-more-deterministic, zlib breakage (and fix) in Windows builds in the middle of this changeset as well
    captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(996cc657dfba)-descendants(e41a37df3892))'], ignoreStderr=True, ignoreExitCode=True) # m-c 84164 - 84288: non-threadsafe build breakage
    captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(30ffa45f9a63)-descendants(fff3dc9478ce))'], ignoreStderr=True, ignoreExitCode=True) # m-c 76465 - 76514: js shell was broken after a gc patch
    captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(a6c636740fb9)-descendants(ca11457ed5fe))'], ignoreStderr=True, ignoreExitCode=True) # m-c 60172 - 60206: a large backout
    captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(be9979b4c10b)-descendants(9f892a5a80fa))'], ignoreStderr=True, ignoreExitCode=True) # m-c 52501 - 53538: jm brokenness
    captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(ff250122fa99)-descendants(723d44ef6eed))'], ignoreStderr=True, ignoreExitCode=True) # m-c 28197 - 28540: m-c to tm merge that broke compilation
    if isMac and macVer() >= [10, 7]:
        captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(e4c82a6b298c)-descendants(036194408a50))'], ignoreStderr=True, ignoreExitCode=True) # m-c 91541 - 91573: clang bustage
        captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(780888b1548c)-descendants(ce10e78d030d))'], ignoreStderr=True, ignoreExitCode=True) # m-c 70985 - 71141: clang bustage
    if 'ionmonkey' in sourceDir:  # Can be removed when IonMonkey lands in mozilla-central - im numbers may need to be changed.
        captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(150159ee5c26)-descendants(fed610aff637))'], ignoreStderr=True, ignoreExitCode=True) # im 91138 - 91258: broken ionmonkey
        captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(300ac3d58291)-descendants(bc1833f2111e))'], ignoreStderr=True, ignoreExitCode=True) # im 93095 - 93098: ionmonkey flags were changed, then later readded but enabled by default to ensure compatibility
        captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(53d0ad70087b)-descendants(73e8ca73e5bd))'], ignoreStderr=True, ignoreExitCode=True) # im 99077 - 99151: broken ionmonkey
        captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(b83b72d7fb86)-descendants(45315f6ccb19))'], ignoreStderr=True, ignoreExitCode=True) # im 99565 - 99571: broken ionmonkey
        captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(23a84dbb258f)-descendants(08187a7ea897))'], ignoreStderr=True, ignoreExitCode=True) # im 101708 - 102667: broken ionmonkey
        captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(b46621aba6fd)-descendants(3da9a96f6c3f))'], ignoreStderr=True, ignoreExitCode=True) # im 102669 - 103054: (this range can replace the one above when IonMonkey merges to m-c) build breakage involving --enable-more-deterministic, zlib breakage (and fix) in Windows builds in the middle of this changeset as well
        if isMac and macVer() >= [10, 7]:
            captureStdout(hgPrefix + ['bisect', '--skip', '(descendants(28be8df0deb7)-descendants(14d9f14b129e))'], ignoreStderr=True, ignoreExitCode=True) # im 72447 - 88354: clang bustage

def earliestKnownWorkingRev(flagsRequired, archNum, valgrindSupport):
    """Returns the oldest version of the shell that can run jsfunfuzz."""

    profilejitBool = '-p' in flagsRequired
    methodjitBool = '-m' in flagsRequired
    methodjitAllBool = '-a' in flagsRequired
    typeInferBool = '-n' in flagsRequired
    debugModeBool = '-d' in flagsRequired
    ionBool = '--ion' in flagsRequired

    # These should be in descending order, or bisection will break at earlier changesets.
    if '--no-ti' in flagsRequired or '--no-ion' in flagsRequired or '--no-jm' in flagsRequired:
        return '300ac3d58291' # IonMonkey flag change (see bug 724751)
    elif '--ion-eager' in flagsRequired:
        return '4ceb3e9961e4' # See bug 683039: "Delay Ion compilation until a function is hot"
    elif ionBool:
        return '43b55878da46' # IonMonkey has not yet landed on m-c, approximate first stable rev w/ --ion -n.
    # FIXME: Somehow test for --enable-root-analysis, or else when it becomes part of the default
    # configuration, this will be the earliest usable changeset.
    #elif ???:
    #    return '7aba0b7a805f' # 98725 on m-c, first rev that has stable --enable-root-analysis builds
    elif typeInferBool and ('-D' in flagsRequired or '--dump-bytecode' in flagsRequired):
        return '0c5ed245a04f' # 75176 on m-c, merge that brought in -D from one side and -n from another
    elif typeInferBool:
        return '228e319574f9' # 74704 on m-c, first rev that has the -n option
    elif '--debugjit' in flagsRequired or '--methodjit' in flagsRequired or '--dump-bytecode' in flagsRequired:
        return 'b1923b866d6a' # 73054 on m-c, first rev that has long variants of many options
    elif '-D' in flagsRequired and isMac and macVer() >= [10, 7]:
        return 'ce10e78d030d' # 71141 on m-c, first rev that has the -D option and compiles under clang
    elif '-D' in flagsRequired:
        return 'e5b92c2bdd2d' # 70991 on m-c, first rev that has the -D option
    elif isMac and macVer() >= [10, 7]:
        return 'd796fb18f555' # 64560 on m-c, first rev that can compile on Lion or greater
    elif methodjitAllBool:
        # This supercedes methodjitBool, -a only works with -m
        return 'f569d49576bb' # 62574 on m-c, first rev that has the -a option
    elif profilejitBool:
        return '339457364540' # 56551 on m-c, first rev that has the -p option
    elif debugModeBool:
        # To bisect farther back, use setDebug(true). See bug 656381 comment 0.
        return 'ea0669bacf12' # 54578 on m-c, first rev that has the -d option
    elif methodjitBool and isWin:
        return '9f2641871ce8' # 53544 on m-c, first rev that can run with pymake and -m
    elif methodjitBool:
        return '547af2626088' # 53105 on m-c, first rev that can run jsfunfuzz-n.js with -m
    elif isWin:
        return 'ea59b927d99f' # 46436 on m-c, first rev that can run pymake on Windows with most recent set of instructions
    elif isMac and [10, 6] <= macVer() < [10, 7] and archNum == "64":
        return "1a44373ccaf6" # 32315 on m-c, config.guess change for snow leopard
    elif isLinux or (isMac and [10, 6] <= macVer() < [10, 7] and archNum == "32"):
        return "db4d22859940" # 24546 on m-c, imacros compilation change
    elif valgrindSupport:
        assert False  # This should no longer be reached since Ubuntu 11.04 has difficulties compiling earlier changesets.
        return "582a62c8f910" # 21512 on m-c, fixed a regexp valgrind warning that is triggered by an empty jsfunfuzz testcase
    else:
        assert False  # This should no longer be reached since Ubuntu 11.04 has difficulties compiling earlier changesets.
        return "8c52a9486c8f" # 21062 on m-c, switch from Makefile.ref to autoconf

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

def ignoreChangesets(hgPre):
    '''Ignores specified changesets that are known to be broken, during hg bisection.'''
    # Skip some busted revisions. It might make sense to avoid (or note) these in checkBlameParents.
    # All numbers in the range excluding boundaries should be broken for some reason.
    # To add to the list, 404.js does not need to exist, WORKINGREV can be default / tip:
    # - (1) will tell you when the brokenness started
    # - (1) autoBisect.py --compilation-failed-label=bad -p -a32 -s WORKINGREV -e FAILINGREV 404.js
    # - (2) will tell you when the brokenness ended
    # - (2) autoBisect.py --compilation-failed-label=bad -p -a32 -s FAILINGREV -e WORKINGREV 404.js
    # Explanation: (descendants(last good changeset)-descendants(first working changeset))
    # Paste numbers into: http://hg.mozilla.org/mozilla-central/rev/<number> to get hgweb link.
    def skipCsets(lastGood, firstWorking):
        '''Skips the changesets present in the range.'''
        captureStdout(hgPre + ['bisect', '--skip',
                '(descendants(' + lastGood + ')-descendants(' + firstWorking + '))'],
            ignoreStderr=True, ignoreExitCode=True)
    skipCsets('b46621aba6fd', '3da9a96f6c3f') # m-c 106605 - 106624: im, zlib, --enable-det breakage
    skipCsets('23a84dbb258f', '08187a7ea897') # m-c 106581 - 106603: broken im
    skipCsets('b83b72d7fb86', '45315f6ccb19') # m-c 106499 - 106505: broken im
    skipCsets('53d0ad70087b', '73e8ca73e5bd') # m-c 106383 - 106457: broken im
    skipCsets('300ac3d58291', 'bc1833f2111e') # m-c 106120 - 106123: im flags rejiggered
    skipCsets('150159ee5c26', 'fed610aff637') # m-c 106007 - 106032: broken im
    skipCsets('ae22e27106b3', '785e4e86798b') # m-c 100867 - 101115: zlib, --enable-det breakage
    skipCsets('996cc657dfba', 'e41a37df3892') # m-c 84164 - 84288: non-threadsafe build breakage
    skipCsets('30ffa45f9a63', 'fff3dc9478ce') # m-c 76465 - 76514: build broken after a gc patch
    skipCsets('a6c636740fb9', 'ca11457ed5fe') # m-c 60172 - 60206: a large backout
    skipCsets('be9979b4c10b', '9f892a5a80fa') # m-c 52501 - 53538: jm brokenness
    skipCsets('ff250122fa99', '723d44ef6eed') # m-c 28197 - 28540: broken m-c to tm merge
    if isMac and macVer() >= [10, 7]:
        skipCsets('28be8df0deb7', '14d9f14b129e') # m-c 72447 - 105867: clang bustage

def earliestKnownWorkingRev(flagsRequired, archNum, valgrindSupport):
    """Returns the oldest version of the shell that can run jsfunfuzz."""

    profilejitBool = '-p' in flagsRequired
    methodjitBool = '-m' in flagsRequired
    methodjitAllBool = '-a' in flagsRequired
    typeInferBool = '-n' in flagsRequired
    debugModeBool = '-d' in flagsRequired
    ionBool = '--ion' in flagsRequired

    assert (not isMac) or (macVer() >= [10, 7])  # Only Lion and above are supported with Clang 4.

    # These should be in descending order, or bisection will break at earlier changesets.
    if '--no-ti' in flagsRequired or '--no-ion' in flagsRequired or '--no-jm' in flagsRequired:
        return '300ac3d58291' # 106120 on m-c, See bug 724751: IonMonkey flag change
    elif ionBool:
        return '43b55878da46' # 105662 on m-c, IonMonkey's approximate first stable rev w/ --ion -n.
    elif '--ion-eager' in flagsRequired:
        return '4ceb3e9961e4' # 105173 on m-c, See bug 683039: "Delay Ion compilation until a function is hot"
    # FIXME: Somehow test for --enable-root-analysis, or else when it becomes part of the default
    # configuration, this will be the earliest usable changeset.
    #elif ???:
    #    return '7aba0b7a805f' # 98725 on m-c, first rev that has stable --enable-root-analysis builds
    elif isMac and macVer() >= [10, 7]:
        return '2046a1f46d40' # 87022 on m-c, first rev that compiles well on Mac under Clang
    elif typeInferBool and ('-D' in flagsRequired or '--dump-bytecode' in flagsRequired):
        return '0c5ed245a04f' # 75176 on m-c, merge that brought in -D from one side and -n from another
    elif typeInferBool:
        return '228e319574f9' # 74704 on m-c, first rev that has the -n option
    elif '--debugjit' in flagsRequired or '--methodjit' in flagsRequired or '--dump-bytecode' in flagsRequired:
        return 'b1923b866d6a' # 73054 on m-c, first rev that has long variants of many options
    elif '-D' in flagsRequired:
        return 'e5b92c2bdd2d' # 70991 on m-c, first rev that has the -D option
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
    else:  # Only Linux should end up here
        return "db4d22859940" # 24546 on m-c, imacros compilation change

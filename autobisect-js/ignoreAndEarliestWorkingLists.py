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
    # Skip some large runs of busted revisions.
    # To add to the list:
    # - (1) will tell you when the brokenness started
    # - (1) autoBisect.py --compilation-failed-label=bad -p -a32 -e FAILINGREV 404.js
    # - (2) will tell you when the brokenness ended
    # - (2) autoBisect.py --compilation-failed-label=bad -p -a32 -s FAILINGREV 404.js
    # (404.js does not need to exist)

    # XXX It might make sense to avoid (or note) these in checkBlameParents.

    # Paste numbers into: http://hg.mozilla.org/mozilla-central/rev/<number> to get hgweb link.

    def hgrange(lastGood, firstWorking):
        return '(descendants(' + lastGood + ')-descendants(' + firstWorking + '))'

    skips = [
        hgrange('be9979b4c10b', '9f892a5a80fa'), # m-c 52501 - 53538: jm brokenness
        hgrange('30ffa45f9a63', 'fff3dc9478ce'), # m-c 76465 - 76514: build broken after a gc patch
        hgrange('c12c8651c10d', '723d44ef6eed'), # m-c to tm merge that broke compilation
        hgrange('996cc657dfba', 'e41a37df3892'), # non-threadsafe build breakage - it might go back earlier than changeset rev d56f08ec0225
        hgrange('ae22e27106b3', '785e4e86798b'), # build breakage involving --enable-more-deterministic, zlib breakage (and fix) in Windows builds in the middle of this changeset as well
        hgrange('150159ee5c26', 'fed610aff637'), # broken ionmonkey
        hgrange('300ac3d58291', 'bc1833f2111e'), # ionmonkey flags were changed, then later readded but enabled by default to ensure compatibility
        hgrange('53d0ad70087b', '73e8ca73e5bd'), # broken ionmonkey
        hgrange('b83b72d7fb86', '45315f6ccb19'), # broken ionmonkey
        hgrange('23a84dbb258f', '08187a7ea897'), # broken ionmonkey
        hgrange('b46621aba6fd', '3da9a96f6c3f'), # broken ionmonkey build breakage involving --enable-more-deterministic, zlib breakage (and fix) in Windows builds in the middle of this changeset as well
    ]

    if isMac and macVer() >= [10, 7]:
        skips.extend([
            hgrange('780888b1548c', 'ce10e78d030d'), # clang
            hgrange('e4c82a6b298c', '036194408a50'), # clang
            hgrange('996e96b4dbcf', '1902eff5df2a'), # broken ionmonkey
            hgrange('7dcb2b6162e5', 'c4dc1640324c'), # broken ionmonkey
        ])

    captureStdout(hgPre + ['bisect', '--skip', " + ".join(skips)],
        ignoreStderr=True, ignoreExitCode=True)


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

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
from subprocesses import isLinux, isMac, macVer

def knownBrokenRanges():
    '''Returns a list of revsets corresponding to known-busted revisions'''
    # Paste numbers into: http://hg.mozilla.org/mozilla-central/rev/<number> to get hgweb link.
    # To add to the list:
    # - (1) will tell you when the brokenness started
    # - (1) autoBisect.py --compilationFailedLabel=bad -e FAILINGREV
    # - (2) will tell you when the brokenness ended
    # - (2) autoBisect.py --compilationFailedLabel=bad -s FAILINGREV

    # ANCIENT FIXME: It might make sense to avoid (or note) these in checkBlameParents.

    def hgrange(lastGood, firstWorking):
        return '(descendants(' + lastGood + ')-descendants(' + firstWorking + '))'

    skips = [
        hgrange('be9979b4c10b', '9f892a5a80fa'), # m-c 52501 - 53538: jm brokenness
        hgrange('30ffa45f9a63', 'fff3dc9478ce'), # m-c 76465 - 76514: build broken after a gc patch
        hgrange('c12c8651c10d', '723d44ef6eed'), # m-c to tm merge that broke compilation
        hgrange('996cc657dfba', 'e41a37df3892'), # non-threadsafe build breakage
        hgrange('ae22e27106b3', '785e4e86798b'), # --enable-more-deterministic and Win zlib breakage
        hgrange('150159ee5c26', 'fed610aff637'), # broken ionmonkey
        hgrange('300ac3d58291', 'bc1833f2111e'), # ion flags changed to ensure compatibility
        hgrange('53d0ad70087b', '73e8ca73e5bd'), # broken ionmonkey
        hgrange('b83b72d7fb86', '45315f6ccb19'), # broken ionmonkey
        hgrange('23a84dbb258f', '08187a7ea897'), # broken ionmonkey
        hgrange('4804d288adae', '9049a4c5c61a'), # broken ionmonkey
        hgrange('0a8867dd72a4', 'a765d833483a'), # Rivertrail work broke non-threadsafe/nspr builds
    ]

    if isMac and macVer() >= [10, 7]:
        skips.extend([
            hgrange('780888b1548c', 'ce10e78d030d'), # clang
            hgrange('e4c82a6b298c', '036194408a50'), # clang
            hgrange('996e96b4dbcf', '1902eff5df2a'), # broken ionmonkey
            hgrange('7dcb2b6162e5', 'c4dc1640324c'), # broken ionmonkey
            hgrange('242a9051f7e9', '14d9f14b129e'), # broken ionmonkey and clang
        ])

    return skips

def earliestKnownWorkingRev(options):
    """Returns the oldest version of the shell that can run jsfunfuzz."""
    assert (not isMac) or (macVer() >= [10, 7])  # Only Lion and above are supported with Clang 4.
    flags = options.paramList

    # These should be in descending order, or bisection will break at earlier changesets.
    # See 7aba0b7a805f, 98725 on m-c, for first stable root analysis builds
    #
    # m-c Python packager changes
    # 6b280e155484 is thus the latest version that can reliably work on all platforms without
    # copying the source files out, i.e. by configuring and compiling in the destination objdir.
    # Thus, consider not copying source files out only when 6b280e155484 at least becomes the
    # minimum changeset that can reliably compile.
    # 119351 - https://hg.mozilla.org/mozilla-central/rev/6b280e155484 works
    # 119350 - https://hg.mozilla.org/mozilla-central/rev/204b95febb13 does not work due to:
    #   "IndexError: list index out of range" error
    # 119349 - https://hg.mozilla.org/mozilla-central/rev/ab31d2237244 does not work due to:
    #   "ImportError: No module named buildconfig" error
    # Note: One could bypass the 119349 error by fully removing the m-c repo, then re-cloning
    #   everytime a build is requested this way, aka a full clobber build.

    if options.enableRootAnalysis or options.isThreadsafe: # Threadsafe result wrong before this rev
        return 'e3799f9cfee8' # 107071 on m-c, first rev with correct getBuildConfiguration details
    elif '--no-ti' in flags or '--no-ion' in flags or '--no-jm' in flags:
        return '300ac3d58291' # 106120 on m-c, See bug 724751: IonMonkey flag change
    elif '--ion' in flags:
        return '43b55878da46' # 105662 on m-c, IonMonkey's approximate first stable rev w/ --ion -n
    elif '--ion-eager' in flags:  # See bug 683039 - Delay Ion compilation until a function is hot
        return '4ceb3e9961e4' # 105173 on m-c
    elif isMac and macVer() >= [10, 7]:
        return '2046a1f46d40' # 87022 on m-c, first rev that compiles well on Mac under Clang
    elif '-n' in flags and ('-D' in flags or '--dump-bytecode' in flags):
        return '0c5ed245a04f' # 75176 on m-c, merge brings in -D from one side and -n from another
    elif '-n' in flags:
        return '228e319574f9' # 74704 on m-c, first rev that has the -n option
    elif '--debugjit' in flags or '--methodjit' in flags or '--dump-bytecode' in flags:
        return 'b1923b866d6a' # 73054 on m-c, first rev that has long variants of many options
    elif '-D' in flags:
        return 'e5b92c2bdd2d' # 70991 on m-c, first rev that has the -D option
    elif '-a' in flags:  # -a only works with -m
        return '11d72b25348d' # 64558 on m-c, first rev that has the -a option
    elif isLinux:
        return 'e8753473cdff' # 61217 on m-c, first rev that compiles properly on Ubuntu 12.10.
    elif '-p' in flags:
        return '339457364540' # 56551 on m-c, first rev that has the -p option
    elif '-d' in flags:  # To bisect farther back, use setDebug(true). See bug 656381 comment 0.
        return 'ea0669bacf12' # 54578 on m-c, first rev that has the -d option
    elif '-m' in flags:
        return '547af2626088' # 53105 on m-c, first rev that can run jsfunfuzz-n.js with -m
    else: # Only Windows should end up here
        return 'ceef8a5c3ca1' # 35725 on m-c, first rev that can build with Visual Studio 2010

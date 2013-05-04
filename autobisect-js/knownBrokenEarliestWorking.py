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

def hgrange(lastGood, firstWorking):
    return '(descendants(' + lastGood + ')-descendants(' + firstWorking + '))'

def knownBrokenRangesBrowser(options):
    skips = [
        hgrange('cc45fdc389df', 'e8938a43c31a'), # Builds with --disable-crashreporter were broken (see bug 779291)
        hgrange('19f154ee6f54', 'd97ecf9f9b84'), # Backed out for bustage
        hgrange('eaa88688e9e8', '7a7e1ca619c2'), # Missing include (affected Jesse's MBP but not Tinderbox)
        hgrange('fbc1e196ca87', '7a9887e1f55e'), # Quick followup for bustage
        hgrange('bfef9b308f92', '991938589ebe'), # A landing required a build fix and a startup-assertion fix
    ]

    return skips

def knownBrokenRanges(options):
    '''Returns a list of revsets corresponding to known-busted revisions'''
    # Paste numbers into: http://hg.mozilla.org/mozilla-central/rev/<number> to get hgweb link.
    # To add to the list:
    # - (1) will tell you when the brokenness started
    # - (1) autoBisect.py --compilationFailedLabel=bad -e FAILINGREV
    # - (2) will tell you when the brokenness ended
    # - (2) autoBisect.py --compilationFailedLabel=bad -s FAILINGREV

    # ANCIENT FIXME: It might make sense to avoid (or note) these in checkBlameParents.

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
        hgrange('7f1ecab23f6f', 'c8e06ab7a39d'), # broken spidermonkey
        hgrange('57449cdf45ad', 'ca0d05c99758'), # broken spidermonkey
        hgrange('8c6ec2899d89', '26653529ea8b'), # broken odinmonkey
    ]

    if isMac and macVer() >= [10, 7]:
        skips.extend([
            hgrange('780888b1548c', 'ce10e78d030d'), # clang
            hgrange('e4c82a6b298c', '036194408a50'), # clang
            hgrange('996e96b4dbcf', '1902eff5df2a'), # broken ionmonkey
            hgrange('7dcb2b6162e5', 'c4dc1640324c'), # broken ionmonkey
            hgrange('242a9051f7e9', '14d9f14b129e'), # broken ionmonkey and clang
        ])

    if options.enableMoreDeterministic:
        skips.extend([
            hgrange('7338d59869c3', 'e963546ec749'), # missing #include -> compile failure
        ])

    if options.enableRootAnalysis:
        skips.extend([
            hgrange('7b516748a65c', '72859dc0fefd'), # broken root analysis builds
        ])

    if options.isThreadsafe:
        skips.extend([
            hgrange('54c6c42eb219', 'fe8429f81df8'), # broken threadsafe builds
        ])

    if options.enableRootAnalysis and options.isThreadsafe and options.enableMoreDeterministic:
        skips.extend([
            hgrange('3eae4564001c', '537fd7f9486b'), # broken builds
        ])

    return skips

def earliestKnownWorkingRevForBrowser(options):
    return '4e852ca66ea0' # or 'd97862fb8e6d' ... either way, oct 2012 on mac :(

def earliestKnownWorkingRev(options, flags):
    '''
    Returns the oldest version of the shell that can run jsfunfuzz and which supports all the flags
    listed in |flags|.
    '''
    assert (not isMac) or (macVer() >= [10, 7])  # Only Lion and above are supported with Clang 4.

    # These should be in descending order, or bisection will break at earlier changesets.
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
    #   everytime a build is requested this way, aka a full clobber build. We should investigate
    #   to see what files get left behind that requires a full clobber. Destroying all .pyc files
    #   might alleviate this.
    # (See fuzzing repo revision ec77c645e97d and nearby for when we tried this in Jan 2013)
    # Moreover, it is more difficult to debug without copying source (e.g. if the dev needs to
    # make some quick modifications in the compilePath directory), or if we need the compilePath
    # sources for gdb to correctly grab line numbers for coredumps after the repo has been updated.

    ionEdgeCaseAnalysisFlag = False
    threadCountFlag = False
    # flags is a list of flags, and the option must exactly match.
    for entry in flags:
        if '--ion-edgecase-analysis=' in entry:
            ionEdgeCaseAnalysisFlag = True
        # What comes after --thread-count= can be any number, so we look for the string instead.
        if '--thread-count=' in entry:
            threadCountFlag = True

    #if options.buildWithAsan:
    #    return '774ba579fd39' # 120418 on m-c, first rev with correct getBuildConfiguration details
    if '--baseline-eager' in flags:
        return 'be125cabea26' # 127353 on m-c, first rev that has the --baseline-eager option
    elif '--no-baseline' in flags:
        return '1c0489e5a302' # 127126 on m-c, first rev that has the --no-baseline option
    elif '--ion-regalloc=backtracking' in flags or '--ion-regalloc=stupid' in flags:
        return 'dc4887f61d2e' # 116100 on m-c, first rev that has the --ion-regalloc=[backtracking|stupid] option. lsra option was already present.
    elif threadCountFlag:
        return 'b4fa8b1f279d' # 114005 on m-c, first rev that has the --thread-count=N option
    elif isMac:
        return 'd97862fb8e6d' # 111938 on m-c, first rev required by Mac w/Xcode 4.6, clang-425.0.24
    elif options.enableRootAnalysis or options.isThreadsafe:
        return 'e3799f9cfee8' # 107071 on m-c, first rev with correct getBuildConfiguration details
    elif '--ion-parallel-compile=' in flags:
        return 'f42381e2760d' # 106714 on m-c, first rev that has the --ion-parallel-compile=[on|off] option
    elif ionEdgeCaseAnalysisFlag:
        return '6c870a497ea4' # 106491 on m-c, first rev that supports --ion-edgecase-analysis=[on|off]
    elif '--no-ti' in flags or '--no-ion' in flags or '--no-jm' in flags:
        return '300ac3d58291' # 106120 on m-c, See bug 724751: IonMonkey flag change
    elif '--ion' in flags:
        return '43b55878da46' # 105662 on m-c, IonMonkey's approximate first stable rev w/ --ion -n
    elif '--ion-eager' in flags:
        return '4ceb3e9961e4' # 105173 on m-c, see bug 683039 - Delay Ion compilation until a function is hot
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

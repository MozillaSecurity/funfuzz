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
from subprocesses import isARMv7l, isLinux, isMac, isMozBuild64, macVer

def hgrange(firstBad, firstGood):
    """Like "firstBad::firstGood", but includes branches/csets that never got the firstGood fix."""
    # NB: mercurial's descendants(x) includes x
    # So this revset expression includes firstBad, but does not include firstGood.
    return '(descendants(' + firstBad + ')-descendants(' + firstGood + '))'

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
        hgrange('d2cce982a7c8', '4a6b8dd4dfe3'), # broken virtualenv
        hgrange('e213c2a01ec2', 'cd67ffb5ca47'), # broken spidermonkey
        hgrange('4ceb3e9961e4', '73e8ca73e5bd'), # broken spidermonkey
    ]

    if isMac and macVer() >= [10, 7]:
        skips.extend([
            hgrange('780888b1548c', 'ce10e78d030d'), # clang
            hgrange('e4c82a6b298c', '036194408a50'), # clang
            hgrange('996e96b4dbcf', '1902eff5df2a'), # broken ionmonkey
            hgrange('7dcb2b6162e5', 'c4dc1640324c'), # broken ionmonkey
            hgrange('242a9051f7e9', '14d9f14b129e'), # broken ionmonkey and clang
            hgrange('c054eef6ba77', 'e02f86260dad'), # clang
        ])

    if isARMv7l:
        skips.extend([
            hgrange('743204c6b245', 'fbd476579542'), # broken ARM builds
        ])

    if isMozBuild64:
        skips.extend([
            hgrange('b4d7497c01c2', 'ef0e134ef78f'), # broken Win64 builds
            hgrange('89a645d498e3', 'ee42c4773641'), # broken Win64 builds
        ])

    if options.enableMoreDeterministic:
        skips.extend([
            hgrange('9ab1119d4596', 'e963546ec749'), # missing #include -> compile failure
            hgrange('7c148efceaf9', '541248fb29e4'), # missing #include -> compile failure
        ])

    if options.enableRootAnalysis:
        skips.extend([
            hgrange('7b516748a65c', '72859dc0fefd'), # broken root analysis builds
        ])

    if options.isThreadsafe:
        skips.extend([
            hgrange('54c6c42eb219', 'fe8429f81df8'), # broken threadsafe builds
            hgrange('07606a1ebf5d', '43f17af3f704'), # --enable-threadsafe was removed
        ])

    if options.enableRootAnalysis and options.isThreadsafe and options.enableMoreDeterministic:
        skips.extend([
            hgrange('3eae4564001c', '537fd7f9486b'), # broken builds
        ])

    # --enable-gcgenerational requires --enable-exact-rooting, so just check for the latter.
    if options.enableExactRooting:
        skips.extend([
            hgrange('f8f0facf81ec', '492e87516012'), # broken exact rooting or GGC
            hgrange('541248fb29e4', '9695f620df74'), # broken exact rooting or GGC
        ])

    return skips

def earliestKnownWorkingRevForBrowser(options):
    return '4e852ca66ea0' # or 'd97862fb8e6d' (same as js below) ... either way, oct 2012 on mac :(

def earliestKnownWorkingRev(options, flags, skipRevs):
    '''
    Returns a revset which evaluates to the first revision of the shell that
    compiles with |options| and runs jsfunfuzz successfully with |flags|.
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

    required = []

    #if options.buildWithAsan:
    #    required.append('774ba579fd39') # 120418 on m-c, first rev with correct getBuildConfiguration details
    #if isMac and macVer() >= [10, 9]:
    #    required.append('d5fa4120ce92') # 152051 on m-c, first rev that builds with Mac 10.9 SDK successfully
    if '--disable-threadsafe' in flags:
        required.append('07606a1ebf5d') # 151079 on m-c, first rev that has the --disable-threadsafe option
    if '--ion-check-range-analysis' in flags:
        required.append('e4a0c6fd1aa9') # 143131 on m-c, first rev that has a stable --ion-check-range-analysis option
    if '--ion-compile-try-catch' in flags:
        required.append('73912c9ba403') # 142172 on m-c, first rev that has a stable --ion-compile-try-catch option
    if '--fuzzing-safe' in flags:
        required.append('0a9314155404') # 135892 on m-c, first rev that has the --fuzzing-safe option
    if '--no-fpu' in flags:
        required.append('f10884c6a91e') # 128312 on m-c, first rev that has the --no-fpu option
    if '--baseline-eager' in flags:
        required.append('be125cabea26') # 127353 on m-c, first rev that has the --baseline-eager option
    if '--no-baseline' in flags:
        required.append('1c0489e5a302') # 127126 on m-c, first rev that has the --no-baseline option
    if '--no-asmjs' in flags:
        required.append('b3d85b68449d') # 124920 on m-c, first rev that has the --no-asmjs option
    if options.enableGcGenerational:
        if options.arch == '32':
            required.append('8d65f437c771') # 124553 on m-c, first rev with working 32-bit Generational GC builds
        elif options.arch == '64':
            required.append('f12876112a28') # 123661 on m-c, first rev with working 64-bit Generational GC builds
    if '--ion-regalloc=backtracking' in flags or '--ion-regalloc=stupid' in flags:
        required.append('dc4887f61d2e') # 116100 on m-c, first rev that has the --ion-regalloc=[backtracking|stupid] option. lsra option was already present.
    if threadCountFlag:
        required.append('b4fa8b1f279d') # 114005 on m-c, first rev that has the --thread-count=N option
    if isMac:
        required.append('d97862fb8e6d') # 111938 on m-c, first rev required by Mac w/Xcode 4.6, clang-425.0.24
    if options.enableRootAnalysis or options.isThreadsafe or options.enableExactRooting:
        required.append('e3799f9cfee8') # 107071 on m-c, first rev with correct getBuildConfiguration details
    if '--ion-parallel-compile=' in flags:
        required.append('f42381e2760d') # 106714 on m-c, first rev that has the --ion-parallel-compile=[on|off] option
    if ionEdgeCaseAnalysisFlag:
        required.append('6c870a497ea4') # 106491 on m-c, first rev that supports --ion-edgecase-analysis=[on|off]
    if '--no-ti' in flags or '--no-ion' in flags or '--no-jm' in flags:
        required.append('300ac3d58291') # 106120 on m-c, See bug 724751: IonMonkey flag change
    if '--ion' in flags:
        required.append('43b55878da46') # 105662 on m-c, IonMonkey's approximate first stable rev w/ --ion -n
    if '--ion-eager' in flags:
        required.append('4ceb3e9961e4') # 105173 on m-c, see bug 683039 - Delay Ion compilation until a function is hot
    if '-n' in flags:
        required.append('228e319574f9') # 74704 on m-c, first rev that has the -n option
    if '--debugjit' in flags or '--methodjit' in flags or '--dump-bytecode' in flags:
        required.append('b1923b866d6a') # 73054 on m-c, first rev that has long variants of many options
    if '-D' in flags:
        required.append('e5b92c2bdd2d') # 70991 on m-c, first rev that has the -D option
    if '-a' in flags:  # -a only works with -m
        required.append('11d72b25348d') # 64558 on m-c, first rev that has the -a option
    if isLinux:
        required.append('e8753473cdff') # 61217 on m-c, first rev that compiles properly on Ubuntu 12.10.
    if '-p' in flags:
        required.append('339457364540') # 56551 on m-c, first rev that has the -p option
    if '-d' in flags:  # To bisect farther back, use setDebug(true). See bug 656381 comment 0.
        required.append('ea0669bacf12') # 54578 on m-c, first rev that has the -d option
    if '-m' in flags:
        required.append('547af2626088') # 53105 on m-c, first rev that can run jsfunfuzz-n.js with -m
    #required.append('232553f741a0') # 52099 on m-c, first rev that can run pymake with -s
    required.append('ceef8a5c3ca1') # 35725 on m-c, first rev that can build with Visual Studio 2010

    return "first((" + commonDescendants(required) + ") - (" + skipRevs + "))"

def commonDescendants(revs):
    return " and ".join("descendants(" + r + ")" for r in revs)

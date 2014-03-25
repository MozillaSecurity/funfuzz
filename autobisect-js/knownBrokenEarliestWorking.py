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
from subprocesses import isARMv7l, isLinux, isMac, isMozBuild64, isWin, macVer

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
        hgrange('b6dc96f18391', '37e29c27e6e8'), # Duplicate symbols with 10.9 SDK, between ICU being built by default and a bug being fixed
        hgrange('ad70d9583d42', 'd0f501b227fc'), # Short bustage
        hgrange('c5906eed61fc', '1c4ac1d21d29'), # Builds succeed but die early in startup
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
        hgrange('0a8867dd72a4', 'a765d833483a'), # Rivertrail work broke non-threadsafe/nspr builds
        hgrange('57449cdf45ad', 'ca0d05c99758'), # broken spidermonkey
        hgrange('8c6ec2899d89', '26653529ea8b'), # broken odinmonkey
        hgrange('d2cce982a7c8', '4a6b8dd4dfe3'), # broken virtualenv
        hgrange('e213c2a01ec2', 'cd67ffb5ca47'), # broken spidermonkey
        hgrange('79a1f60d83df', 'a88f40be25e7'), # broken spidermonkey
        hgrange('4110a8986a2a', '9f64519c330f'), # broken cross-compile and ICU, very problematic
        hgrange('3b9e118ded0f', '48161187ac9a'), # --disable-threadsafe was broken
        hgrange('b0678affef03', '77d06ee9ac48'), # broken standalone js shells with ICU
        hgrange('7cff27cb2845', 'ff5ca7959511'), # broken build config w/ NSPR
    ]

    if isMac and macVer() >= [10, 7]:
        skips.extend([
            hgrange('c054eef6ba77', 'e02f86260dad'), # clang
        ])

    if isARMv7l:
        skips.extend([
            hgrange('743204c6b245', 'fbd476579542'), # broken ARM builds
        ])

    if isWin:
        skips.extend([
            hgrange('f6d5a48271b6', 'dc128b242d8a'), # broken Windows builds due to ICU
            hgrange('17c463691232', 'f76b7bc18dbc'), # broken Windows builds due to build breakage
        ])

    if isMozBuild64:
        skips.extend([
            hgrange('b4d7497c01c2', 'ef0e134ef78f'), # broken Win64 builds
            hgrange('89a645d498e3', 'ee42c4773641'), # broken Win64 builds
            hgrange('77d06ee9ac48', 'e7bb99d245e8'), # broken Win64 builds, due to moz.build error
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

    if not options.isThreadsafe:
        skips.extend([
            hgrange('d86f10836597', 'f6d5a48271b6'), # broken non-threadsafe after ts became default
            hgrange('d633e3ff2013', 'bcbe93f41547'), # broken non-threadsafe after ts became default
            hgrange('dbeea0e93b56', 'b980c2dee2e7'), # broken non-threadsafe after ts became default
            hgrange('995f7402235b', '6c899a1064f3'), # broken non-threadsafe after ts became default
            hgrange('d2c4ae312b66', 'abfaf0ccae19'), # broken non-threadsafe after ts became default
        ])

    # This has been moved to a global ignore range. JSBugMon passes in --disable-threadsafe directly
    # so the way to solve this is if knownBrokenEarliestWorking.py knows what configure parameters
    # have been passed.
    #if not options.isThreadsafe:
    #    skips.extend([
    #        hgrange('3b9e118ded0f', '48161187ac9a'), # --disable-threadsafe was broken
    #    ])

    if options.enableRootAnalysis and options.isThreadsafe and options.enableMoreDeterministic:
        skips.extend([
            hgrange('3eae4564001c', '537fd7f9486b'), # broken builds
        ])

    return skips

def earliestKnownWorkingRevForBrowser(options):
    if isMac and macVer() >= [10, 9]:
        return '1c4ac1d21d29' # beacc621ec68 fixed 10.9 builds, but landed in the middle of unrelated bustage
    return '4e852ca66ea0' # or 'd97862fb8e6d' (same as js below) ... either way, oct 2012 on mac :(

def earliestKnownWorkingRev(options, flags, skipRevs):
    '''
    Returns a revset which evaluates to the first revision of the shell that
    compiles with |options| and runs jsfunfuzz successfully with |flags|.
    '''
    assert (not isMac) or (macVer() >= [10, 7])  # Only Lion and above are supported with Clang 4.

    # These should be in descending order, or bisection will break at earlier changesets.

    threadCountFlag = False
    # flags is a list of flags, and the option must exactly match.
    for entry in flags:
        # What comes after --thread-count= can be any number, so we look for the string instead.
        if '--thread-count=' in entry:
            threadCountFlag = True

    required = []

    #if options.buildWithAsan:
    #    required.append('774ba579fd39') # 120418 on m-c, first rev with correct getBuildConfiguration details
    #if isMac and macVer() >= [10, 9]:
    #    required.append('d5fa4120ce92') # 152051 on m-c, first rev that builds with Mac 10.9 SDK successfully
    if options.disableExactRooting or options.enableGcGenerational:
        required.append('6f7227918e79') # 164088 on m-c, first rev that has stable forward-compatible compilation options for GGC
    if isWin:
        required.append('1a1968da61b3') # 163224 on m-c, first rev that builds on Windows successfully after build config changes
    if isMac and macVer() >= [10, 9]:
        required.append('37e29c27e6e8') # 150707 on m-c, first rev that builds with Intl (built by default) on Mac 10.9 successfully
    if '--ion-check-range-analysis' in flags:
        required.append('e4a0c6fd1aa9') # 143131 on m-c, first rev that has a stable --ion-check-range-analysis option
    if '--fuzzing-safe' in flags or '--ion-parallel-compile=' in flags:
        # --fuzzing-safe and --ion-parallel-compile=off generally are required flags for compareJIT
        # autoBisect acts funny when in the region between m-c rev f42381e2760d and 0a9314155404,
        # so we should just use the later revision as the start revision.
        required.append('0a9314155404') # 135892 on m-c, first rev that has the --fuzzing-safe option
    if '--no-fpu' in flags:
        required.append('f10884c6a91e') # 128312 on m-c, first rev that has the --no-fpu option
    if '--baseline-eager' in flags:
        required.append('be125cabea26') # 127353 on m-c, first rev that has the --baseline-eager option
    if '--no-baseline' in flags:
        required.append('1c0489e5a302') # 127126 on m-c, first rev that has the --no-baseline option
    if '--no-asmjs' in flags:
        required.append('b3d85b68449d') # 124920 on m-c, first rev that has the --no-asmjs option
    if '--ion-regalloc=backtracking' in flags or '--ion-regalloc=stupid' in flags:
        required.append('dc4887f61d2e') # 116100 on m-c, first rev that has the --ion-regalloc=[backtracking|stupid] option. lsra option was already present.
    if threadCountFlag:
        required.append('b4fa8b1f279d') # 114005 on m-c, first rev that has the --thread-count=N option
    if isMac and [10, 7] <= macVer() < [10, 9]:
        required.append('d97862fb8e6d') # 111938 on m-c, first rev required by Mac w/Xcode 4.6, clang-425.0.24
    required.append('e3799f9cfee8') # 107071 on m-c, first rev with correct getBuildConfiguration details

    return "first((" + commonDescendants(required) + ") - (" + skipRevs + "))"

def commonDescendants(revs):
    return " and ".join("descendants(" + r + ")" for r in revs)

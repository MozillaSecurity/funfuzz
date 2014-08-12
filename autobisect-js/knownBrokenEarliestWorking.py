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
from subprocesses import isARMv7l, isMac, isMozBuild64, isWin, macVer

def hgrange(firstBad, firstGood):
    """Like "firstBad::firstGood", but includes branches/csets that never got the firstGood fix."""
    # NB: mercurial's descendants(x) includes x
    # So this revset expression includes firstBad, but does not include firstGood.
    # NB: hg log -r "(descendants(id(badddddd)) - descendants(id(baddddddd)))" happens to return the empty set, like we want"
    return '(descendants(id(' + firstBad + '))-descendants(id(' + firstGood + ')))'

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
    # Paste numbers into: https://hg.mozilla.org/mozilla-central/rev/<number> to get hgweb link.
    # To add to the list:
    # - (1) will tell you when the brokenness started
    # - (1) autoBisect.py --compilationFailedLabel=bad -e FAILINGREV
    # - (2) will tell you when the brokenness ended
    # - (2) autoBisect.py --compilationFailedLabel=bad -s FAILINGREV

    # ANCIENT FIXME: It might make sense to avoid (or note) these in checkBlameParents.

    skips = [
        hgrange('d633e3ff2013', 'bcbe93f41547'), # Fx29, broken non-threadsafe
        hgrange('dbeea0e93b56', 'b980c2dee2e7'), # Fx29, broken non-threadsafe
        hgrange('995f7402235b', '6c899a1064f3'), # Fx30, broken non-threadsafe
        hgrange('d2c4ae312b66', 'abfaf0ccae19'), # Fx30, broken non-threadsafe
        hgrange('7cff27cb2845', 'ff5ca7959511'), # Fx30, broken build config w/ NSPR
        hgrange('07c0cf637290', 'f2adbe2a41c0'), # Fx31, broken non-threadsafe
        hgrange('99a6ee6466f5', '5c9119729bbf'), # Fx32, unstable spidermonkey
        hgrange('573458d10426', '5a50315d4d7d'), # Fx33, broken non-threadsafe
        hgrange('6b285759568c', 'e498b157651e'), # Fx34, broken ICU
    ]

    if isARMv7l:
        skips.extend([
            hgrange('688d526f9313', '280aa953c868'), # Fx29-30, broken ARM builds
            hgrange('35e7af3e86fd', 'a393ec07bc6a'), # Fx32, broken ARM builds
        ])

    if isWin:
        skips.extend([
            hgrange('f6d5a48271b6', 'dc128b242d8a'), # Fx29, broken Windows builds due to ICU
            hgrange('17c463691232', 'f76b7bc18dbc'), # Fx29-30, build breakage
            hgrange('d959285c827e', 'edf5e2dc9198'), # Fx33, build breakage
        ])

    if isMozBuild64:
        skips.extend([
            hgrange('77d06ee9ac48', 'e7bb99d245e8'), # Fx28-29, breakage due to moz.build error
        ])

    if options.enableMoreDeterministic:
        skips.extend([
            hgrange('4a04ca5ed7d3', '406904577dfc'), # Fx33, see bug 1030014
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

    offthreadCompileFlag = asmNopFillFlag = asmPoolMaxOffsetFlag = False
    # flags is a list of flags, and the option must exactly match.
    for entry in flags:
        # What comes after these flags needs to be a number, so we look for the string instead.
        if '--ion-offthread-compile=' in entry:
            offthreadCompileFlag = True
        elif '--arm-asm-nop-fill=' in entry:
            asmNopFillFlag = True
        elif '--asm-pool-max-offset=' in entry:
            asmPoolMaxOffsetFlag = True

    required = []

    if '--no-threads' in flags:
        required.append('e8558ecd9b16') # m-c 195999 Fx34, 1st w/--no-threads, see bug 1031529
    if '--enable-nspr-build' in flags:
        required.append('a459b02a9ca4') # m-c 194734 Fx33, 1st w/--enable-nspr-build, see bug 975011
    if asmPoolMaxOffsetFlag:
        required.append('f114c4101f02') # m-c 194525 Fx33, 1st w/--asm-pool-max-offset=1024, see bug 1026919
    if asmNopFillFlag:
        required.append('f1bacafe789c') # m-c 192164 Fx33, 1st w/--arm-asm-nop-fill=0, see bug 1020834
    if offthreadCompileFlag:
        required.append('f0d67b1ccff9') # m-c 188901 Fx33, 1st w/--ion-offthread-compile=off, see bug 1020364
    if '--no-native-regexp' in flags:
        required.append('43acd23f5a98') # m-c 183413 Fx32, 1st w/--no-native-regexp, see bug 976446
    if options.enableArmSimulator:
        required.append('5ad5f92387a2') # m-c 179476 Fx31, 1st w/relevant getBuildConfiguration entry, see bug 998596
    if options.disableGcGenerational:
        required.append('52f43e3f552f') # m-c 175600 Fx31, 1st w/--disable-gcgenerational option, see bug 619558
    if options.disableExactRooting:
        required.append('6f7227918e79') # m-c 164088 Fx28, 1st w/stable forward-compatible compilation options for GGC, see bug 753203
    if isWin:
        required.append('1a1968da61b3') # m-c 163224 Fx29, 1st w/successful Win builds after build config changes, see bug 950298
    required.append('df3c2a1e86d3') # m-c 160479 Fx29, prior non-threadsafe builds act weirdly with threadsafe-only flags from later revs, see bug 927685

    return "first((" + commonDescendants(required) + ") - (" + skipRevs + "))"

def commonDescendants(revs):
    return " and ".join("descendants(" + r + ")" for r in revs)

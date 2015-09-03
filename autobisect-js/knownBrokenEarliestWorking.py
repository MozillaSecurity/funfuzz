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
import subprocesses as sps


def hgrange(firstBad, firstGood):
    """Like "firstBad::firstGood", but includes branches/csets that never got the firstGood fix."""
    # NB: mercurial's descendants(x) includes x
    # So this revset expression includes firstBad, but does not include firstGood.
    # NB: hg log -r "(descendants(id(badddddd)) - descendants(id(baddddddd)))" happens to return the empty set, like we want"
    return '(descendants(id(' + firstBad + '))-descendants(id(' + firstGood + ')))'


def knownBrokenRangesBrowser(options):
    skips = [
        hgrange('cc45fdc389df', 'e8938a43c31a'),  # Builds with --disable-crashreporter were broken (see bug 779291)
        hgrange('19f154ee6f54', 'd97ecf9f9b84'),  # Backed out for bustage
        hgrange('eaa88688e9e8', '7a7e1ca619c2'),  # Missing include (affected Jesse's MBP but not Tinderbox)
        hgrange('fbc1e196ca87', '7a9887e1f55e'),  # Quick followup for bustage
        hgrange('bfef9b308f92', '991938589ebe'),  # A landing required a build fix and a startup-assertion fix
        hgrange('b6dc96f18391', '37e29c27e6e8'),  # Duplicate symbols with 10.9 SDK, between ICU being built by default and a bug being fixed
        hgrange('ad70d9583d42', 'd0f501b227fc'),  # Short bustage
        hgrange('c5906eed61fc', '1c4ac1d21d29'),  # Builds succeed but die early in startup
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
        hgrange('dbeea0e93b56', 'b980c2dee2e7'),  # Fx29, broken non-threadsafe
        hgrange('464e261cbcbe', '8838fe37b98d'),  # Fx29, broken non-threadsafe
        hgrange('d633e3ff2013', 'bcbe93f41547'),  # Fx29, broken non-threadsafe
        hgrange('f97076de7eb0', '609fa13b17d0'),  # Fx29, broken non-threadsafe
        hgrange('995f7402235b', '6c899a1064f3'),  # Fx30, broken non-threadsafe
        hgrange('d2c4ae312b66', 'abfaf0ccae19'),  # Fx30, broken non-threadsafe
        hgrange('7cff27cb2845', 'ff5ca7959511'),  # Fx30, broken build config w/ NSPR
        hgrange('07c0cf637290', 'f2adbe2a41c0'),  # Fx31, broken non-threadsafe
        hgrange('99a6ee6466f5', '5c9119729bbf'),  # Fx32, unstable spidermonkey
        hgrange('93dce4b831f3', '143ce643d1b3'),  # Fx32, asserts when run with --thread-count=1
        hgrange('573458d10426', '5a50315d4d7d'),  # Fx33, broken non-threadsafe
        hgrange('6b285759568c', 'e498b157651e'),  # Fx34, broken ICU
        hgrange('03242a11d044', '31714af41f2c'),  # Fx35, broken spidermonkey due to let changes
        hgrange('b160657339f8', '06d07689a043'),  # Fx36, unstable spidermonkey
        hgrange('1c9c64027cac', 'ef7a85ec6595'),  # Fx37, unstable spidermonkey
        hgrange('7c25be97325d', 'd426154dd31d'),  # Fx38, broken spidermonkey
        hgrange('da286f0f7a49', '62fecc6ab96e'),  # Fx39, broken spidermonkey
        hgrange('8a416fedec44', '7f9252925e26'),  # Fx41, broken spidermonkey
    ]

    if sps.isMac:
        skips.extend([
            hgrange('5e45fba743aa', '8e5d8f34c53e'),  # Fx39, broken Mac builds due to jemalloc
        ])

    if options.enableMoreDeterministic:
        skips.extend([
            hgrange('4a04ca5ed7d3', '406904577dfc'),  # Fx33, see bug 1030014
            hgrange('752ce35b166b', 'e6e63113336d'),  # Fx35, see bug 1069704
            hgrange('1d672188b8aa', 'ea7dabcd215e'),  # Fx40, see bug 1149739
        ])

    return skips


def earliestKnownWorkingRevForBrowser(options):
    if sps.isMac and sps.macVer() >= [10, 9]:
        return '1c4ac1d21d29'  # beacc621ec68 fixed 10.9 builds, but landed in the middle of unrelated bustage
    return '4e852ca66ea0'  # or 'd97862fb8e6d' (same as js below) ... either way, oct 2012 on mac :(


def earliestKnownWorkingRev(options, flags, skipRevs):
    '''
    Returns a revset which evaluates to the first revision of the shell that
    compiles with |options| and runs jsfunfuzz successfully with |flags|.
    '''
    assert (not sps.isMac) or (sps.macVer() >= [10, 7])  # Only Lion and above are supported with Clang 4.

    # These should be in descending order, or bisection will break at earlier changesets.

    offthreadCompileFlag = gczealValueFlag = False
    # flags is a list of flags, and the option must exactly match.
    for entry in flags:
        # What comes after these flags needs to be a number, so we look for the string instead.
        if '--ion-offthread-compile=' in entry:
            offthreadCompileFlag = True
        elif '--gc-zeal=' in entry:
            gczealValueFlag = True

    required = []

    if "--ion-instruction-reordering=on" in flags:
        required.append('59d2f2e62420')  # m-c 259672 Fx43, 1st w/--ion-instruction-reordering=on, see bug 1195545
    if "--ion-shared-stubs=on" in flags:
        required.append('3655d19ce241')  # m-c 257573 Fx43, 1st w/--ion-shared-stubs=on, see bug 1168756
    if options.enableSimulatorArm64:
        # This should get updated whenever ARM64 builds are stable, probably ~end-June 2015
        required.append('25e99bc12482')  # m-c 249239 Fx41, 1st w/--enable-simulator=[arm|arm64|mips], see bug 1173992
    if "--ion-regalloc=testbed" in flags:
        required.append('47e92bae09fd')  # m-c 248962 Fx41, 1st w/--ion-regalloc=testbed, see bug 1170840
    if '--non-writable-jitcode' in flags:
        required.append('b46d6692fe50')  # m-c 248578 Fx41, 1st w/--non-writable-jitcode, see bug 977805
    if '--no-unboxed-objects' in flags:
        required.append('322487136b28')  # m-c 244297 Fx41, 1st w/--no-unboxed-objects, see bug 1162199
    if '--unboxed-arrays' in flags:
        required.append('020c6a559e3a')  # m-c 242167 Fx40, 1st w/--unboxed-arrays, see bug 1146597
    if '--ion-extra-checks' in flags:
        required.append('cdf93416b39a')  # m-c 234228 Fx39, 1st w/--ion-extra-checks, see bug 1139152
    if '--no-cgc' in flags:
        required.append('b63d7e80709a')  # m-c 227705 Fx38, 1st w/--no-cgc, see bug 1126769 and see bug 1129233
    if sps.isWin:
        required.append('8937836d3c93')  # m-c 226774 Fx38, 1st w/ successful MSVC 2013 and 2015 builds, see bug 1119072
    if sps.isLinux:
        required.append('6ec9033a4535')  # m-c 217796 Fx36, previous builds fail on some Linux variants with different compiler versions
    if '--ion-sink=on' in flags:
        required.append('9188c8b7962b')  # m-c 217242 Fx36, 1st w/--ion-sink=on, see bug 1093674
    if gczealValueFlag:
        required.append('03c6a758c9e8')  # m-c 216625 Fx36, 1st w/--gc-zeal=14, see bug 1101602
    if '--no-incremental-gc' in flags:
        required.append('35025fd9e99b')  # m-c 211115 Fx36, 1st w/--no-incremental-gc, see bug 958492
    if '--ion-loop-unrolling=on' in flags:
        required.append('aa33f4725177')  # m-c 198804 Fx34, 1st w/--ion-loop-unrolling=on, see bug 1039458
    if '--no-threads' in flags:
        required.append('e8558ecd9b16')  # m-c 195999 Fx34, 1st w/--no-threads, see bug 1031529
    if options.enableNsprBuild:
        required.append('a459b02a9ca4')  # m-c 194734 Fx33, 1st w/--enable-nspr-build, see bug 975011
    if offthreadCompileFlag:
        required.append('f0d67b1ccff9')  # m-c 188901 Fx33, 1st w/--ion-offthread-compile=off, see bug 1020364
    if '--no-native-regexp' in flags:
        required.append('43acd23f5a98')  # m-c 183413 Fx32, 1st w/--no-native-regexp, see bug 976446
    if options.enableSimulatorArm32:
        # --enable-arm-simulator became --enable-simulator=arm in rev 25e99bc12482
        # but unknown flags are ignored, so we compile using both till Fx38 ESR is deprecated
        required.append('5ad5f92387a2')  # m-c 179476 Fx31, see bug 1173992
    required.append('f9374ef0fbed')  # m-c 163848 Fx29, prior builds have issues with Xcode 6.3 and above

    return "first((" + commonDescendants(required) + ") - (" + skipRevs + "))"


def commonDescendants(revs):
    return " and ".join("descendants(" + r + ")" for r in revs)

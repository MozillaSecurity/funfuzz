#!/usr/bin/env python
# coding=utf-8
# pylint: disable=invalid-name,missing-docstring,too-many-branches
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import absolute_import, print_function

# pylint issue 73 https://git.io/vQAhf
from distutils.version import StrictVersion  # pylint: disable=import-error,no-name-in-module

from ..util import subprocesses as sps


def hgrange(firstBad, firstGood):
    """Like "firstBad::firstGood", but includes branches/csets that never got the firstGood fix."""
    # NB: mercurial's descendants(x) includes x
    # So this revset expression includes firstBad, but does not include firstGood.
    # NB: hg log -r "(descendants(id(badddddd)) - descendants(id(baddddddd)))" happens to return the empty set,
    # like we want"
    return '(descendants(id(' + firstBad + '))-descendants(id(' + firstGood + ')))'


def knownBrokenRanges(options):
    """Return a list of revsets corresponding to known-busted revisions."""
    # Paste numbers into: https://hg.mozilla.org/mozilla-central/rev/<number> to get hgweb link.
    # To add to the list:
    # - (1) will tell you when the brokenness started
    # - (1) autoBisect.py --compilationFailedLabel=bad -e FAILINGREV
    # - (2) will tell you when the brokenness ended
    # - (2) autoBisect.py --compilationFailedLabel=bad -s FAILINGREV

    # ANCIENT FIXME: It might make sense to avoid (or note) these in checkBlameParents.

    skips = [
        hgrange('b160657339f8', '06d07689a043'),  # Fx36, unstable spidermonkey
        hgrange('1c9c64027cac', 'ef7a85ec6595'),  # Fx37, unstable spidermonkey
        hgrange('7c25be97325d', 'd426154dd31d'),  # Fx38, broken spidermonkey
        hgrange('da286f0f7a49', '62fecc6ab96e'),  # Fx39, broken spidermonkey
        hgrange('8a416fedec44', '7f9252925e26'),  # Fx41, broken spidermonkey
        hgrange('3bcc3881b95d', 'c609df6d3895'),  # Fx44, broken spidermonkey
        hgrange('d3a026933bce', '5fa834fe9b96'),  # Fx52, broken spidermonkey
    ]

    if sps.isMac:
        skips.extend([
            hgrange('5e45fba743aa', '8e5d8f34c53e'),  # Fx39, broken Mac builds due to jemalloc
            hgrange('9b7c2bcabd4e', '43b1143f2930'),  # Fx49-50, broken Mac 10.12 builds
        ])
        if options.enableSimulatorArm32:
            skips.extend([
                hgrange('3a580b48d1ad', '20c9570b0734'),  # Fx43, broken 32-bit Mac ARM-simulator builds
                hgrange('f6fddb22a8b5', '120d57d59f38'),  # Fx51, broken 32-bit Mac ARM-simulator builds
            ])

    if sps.isLinux or sps.isMac:
        skips.extend([
            # Clang failure - probably recent versions of GCC as well.
            hgrange('5232dd059c11', 'ed98e1b9168d'),  # Fx41, see bug 1140482
        ])

    if sps.isLinux and not options.disableProfiling:
        skips.extend([
            # To bypass the following month-long breakage, use "--disable-profiling"
            hgrange('aa1da5ed8a07', '5a03382283ae'),  # Fx54-55, see bug 1339190
        ])

    if sps.isWin10:
        skips.extend([
            hgrange('be8b0845f283', 'db3ed1fdbbea'),  # Fx50, see bug 1289679
        ])

    if not options.enableDbg:
        skips.extend([
            hgrange('a048c55e1906', 'ddaa87cfd7fa'),  # Fx46, broken opt builds w/ --enable-gczeal
        ])

    if options.enableMoreDeterministic:
        skips.extend([
            hgrange('1d672188b8aa', 'ea7dabcd215e'),  # Fx40, see bug 1149739
        ])

    if options.enableSimulatorArm32:
        skips.extend([
            hgrange('3a580b48d1ad', '20c9570b0734'),  # Fx43, broken 32-bit ARM-simulator builds
            hgrange('f35d1107fe2e', 'bdf975ad2fcd'),  # Fx45, broken 32-bit ARM-simulator builds
            hgrange('6c37be9cee51', '4548ba932bde'),  # Fx50, broken 32-bit ARM-simulator builds
        ])

    return skips


def earliestKnownWorkingRev(options, flags, skipRevs):
    """Return a revset which evaluates to the first revision of the shell that compiles with |options|
    and runs jsfunfuzz successfully with |flags|."""
    assert (not sps.isMac) or (sps.macVer() >= [10, 10])  # Only support at least Mac OS X 10.10

    # These should be in descending order, or bisection will break at earlier changesets.
    gczealValueFlag = False
    # flags is a list of flags, and the option must exactly match.
    for entry in flags:
        # What comes after these flags needs to be a number, so we look for the string instead.
        if '--gc-zeal=' in entry:
            gczealValueFlag = True

    required = []

    if sps.isWin:
        required.append('530f7bd28399')  # m-c 369571 Fx56, 1st w/ successful MSVC 2017 builds, see bug 1356493
    # Note that the sed version check only works with GNU sed, not BSD sed found in macOS.
    if sps.isLinux and StrictVersion(sps.verCheck('sed').split()[3]) >= StrictVersion('4.3'):
        required.append('ebcbf47a83e7')  # m-c 328765 Fx53, 1st w/ working builds using sed 4.3+ found on Ubuntu 17.04+
    if options.disableProfiling:
        required.append('800a887c705e')  # m-c 324836 Fx53, 1st w/ --disable-profiling, see bug 1321065
    if options.buildWithClang and sps.isWin:
        required.append('3b26d191d84e')  # m-c 316445 Fx52, 1st w/ reliable Clang 3.9.0 builds on Windows
    if "--wasm-always-baseline" in flags:
        required.append('893294e2a387')  # m-c 301769 Fx50, 1st w/--wasm-always-baseline, see bug 1232205
    if '--ion-aa=flow-sensitive' in flags or '--ion-aa=flow-insensitive' in flags:
        # m-c 295435 Fx49, 1st w/--ion-aa=[flow-sensitive|flow-insensitive], see bug 1255008
        required.append('c0c1d923c292')
    if "--ion-pgo=on" in flags:
        required.append('b0a0ff5fa705')  # m-c 272274 Fx45, 1st w/--ion-pgo=on, see bug 1209515
    if options.buildWithAsan:
        required.append('d4e0e0e5d26d')  # m-c 268534 Fx44, 1st w/ reliable ASan builds w/ ICU, see bug 1214464
    if "--ion-sincos=on" in flags:
        required.append('3dec2b935295')  # m-c 262544 Fx43, 1st w/--ion-sincos=on, see bug 984018
    if "--ion-instruction-reordering=on" in flags:
        required.append('59d2f2e62420')  # m-c 259672 Fx43, 1st w/--ion-instruction-reordering=on, see bug 1195545
    if "--ion-shared-stubs=on" in flags:
        required.append('3655d19ce241')  # m-c 257573 Fx43, 1st w/--ion-shared-stubs=on, see bug 1168756
    if options.enableSimulatorArm32 or options.enableSimulatorArm64:
        # For ARM64: This should get updated whenever ARM64 builds are stable, probably ~end-June 2015
        # To bisect manually slightly further, use "-s dc4b163f7db7 -e f50a771d7d1b" and:
        # Also comment out from:
        # https://github.com/MozillaSecurity/funfuzz/blob/bbc5d5c74d/autobisect-js/autoBisect.py#L176
        # (line 176) to line 180.
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
    if sps.isLinux:
        required.append('bcacb5692ad9')  # m-c 222786 Fx37, 1st w/ successful GCC 5.2.x builds on Ubuntu 15.10 onwards
    if '--ion-sink=on' in flags:
        required.append('9188c8b7962b')  # m-c 217242 Fx36, 1st w/--ion-sink=on, see bug 1093674
    if gczealValueFlag:
        required.append('03c6a758c9e8')  # m-c 216625 Fx36, 1st w/--gc-zeal=14, see bug 1101602
    required.append('dc4b163f7db7')  # m-c 213475 Fx36, prior builds have issues with Xcode 7.0 and above

    return "first((" + commonDescendants(required) + ") - (" + skipRevs + "))"


def commonDescendants(revs):
    return " and ".join("descendants(" + r + ")" for r in revs)

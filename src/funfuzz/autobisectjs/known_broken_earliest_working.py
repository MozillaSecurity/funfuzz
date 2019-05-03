# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Known broken changeset ranges of SpiderMonkey are specified in this file.
"""

import platform

from pkg_resources import parse_version


def hgrange(first_bad, first_good):  # pylint: disable=missing-param-doc,missing-return-doc,missing-return-type-doc
    # pylint: disable=missing-type-doc
    """Like "first_bad::first_good", but includes branches/csets that never got the first_good fix."""
    # NB: mercurial's descendants(x) includes x
    # So this revset expression includes first_bad, but does not include first_good.
    # NB: hg log -r "(descendants(id(badddddd)) - descendants(id(baddddddd)))" happens to return the empty set,
    # like we want"
    return f"(descendants(id({first_bad}))-descendants(id({first_good})))"


def known_broken_ranges(options):  # pylint: disable=missing-param-doc,missing-return-doc,missing-return-type-doc
    # pylint: disable=missing-type-doc
    """Return a list of revsets corresponding to known-busted revisions."""
    # Paste numbers into: https://hg.mozilla.org/mozilla-central/rev/<number> to get hgweb link.
    # To add to the list:
    # - (1) will tell you when the brokenness started
    # - (1) <python executable> -m funfuzz.autobisectjs --compilationFailedLabel=bad -e FAILINGREV
    # - (2) will tell you when the brokenness ended
    # - (2) <python executable> -m funfuzz.autobisectjs --compilationFailedLabel=bad -s FAILINGREV

    # ANCIENT FIXME: It might make sense to avoid (or note) these in checkBlameParents.

    skips = [
        hgrange("4c72627cfc6c", "926f80f2c5cc"),  # Fx60, broken spidermonkey
        hgrange("1fb7ddfad86d", "5202cfbf8d60"),  # Fx63, broken spidermonkey
        hgrange("aae4f349fa58", "c5fbbf959e23"),  # Fx64, broken spidermonkey
        hgrange("f611bc50d11c", "39d0c50a2209"),  # Fx66, broken spidermonkey
    ]

    if platform.system() == "Darwin":
        skips.extend([
            hgrange("3d0236f985f8", "32cef42080b1"),  # Fx68, see bug 1544418
        ])

    if platform.system() == "Linux":
        skips.extend([
            # Failure specific to GCC 5 (and probably earlier) - supposedly works on GCC 6
            hgrange("e94dceac8090", "516c01f62d84"),  # Fx56-57, see bug 1386011
        ])
        if platform.machine() == "aarch64":
            skips.extend([
                hgrange("e8bb22053e65", "999757e9e5a5"),  # Fx54, see bug 1336344
            ])
        if not options.disableProfiling:
            skips.extend([
                # To bypass the following month-long breakage, use "--disable-profiling"
                hgrange("aa1da5ed8a07", "5a03382283ae"),  # Fx54-55, see bug 1339190
            ])

    if not options.enableDbg:
        skips.extend([
            hgrange("c5561749c1c6", "f4c15a88c937"),  # Fx58-59, broken opt builds w/ --enable-gczeal
            hgrange("247e265373eb", "e4aa68e2a85b"),  # Fx66, broken opt builds w/ --enable-gczeal
        ])

    if options.enableMoreDeterministic:
        skips.extend([
            hgrange("427b854cdb1c", "4c4e45853808"),  # Fx68, see bug 1542980
        ])

    if options.enableSimulatorArm32:
        skips.extend([
            hgrange("284002382c21", "05669ce25b03"),  # Fx57-61, broken 32-bit ARM-simulator builds
        ])

    return skips


def earliest_known_working_rev(options, flags, skip_revs):  # pylint: disable=missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc,too-many-branches,too-complex,too-many-statements
    """Return a revset which evaluates to the first revision of the shell that compiles with |options|
    and runs jsfunfuzz successfully with |flags|."""
    # Only support at least Mac OS X 10.13
    assert (not platform.system() == "Darwin") or (parse_version(platform.mac_ver()[0]) >= parse_version("10.13"))

    cpu_count_flag = False
    for entry in flags:  # flags is a list of flags, and the option must exactly match.
        if "--cpu-count=" in entry:
            cpu_count_flag = True

    required = []

    # These should be in descending order, or bisection will break at earlier changesets.
    if "--enable-experimental-fields" in flags:
        required.append("7a1ad6647c22")  # m-c 463705 Fx67, 1st w/--enable-experimental-fields, see bug 1529758
    if set(["--wasm-compiler=none", "--wasm-compiler=baseline+ion", "--wasm-compiler=baseline",
            "--wasm-compiler=ion"]).intersection(flags):
        required.append("48dc14f79fb0")  # m-c 455252 Fx66, 1st w/--wasm-compiler=none/<other options>, see bug 1509441
    if "--more-compartments" in flags:
        required.append("450b8f0cbb4e")  # m-c 453627 Fx66, 1st w/--more-compartments, see bug 1518753
    if "--no-streams" in flags:
        required.append("c6a8b4d451af")  # m-c 442977 Fx65, 1st w/ working --no-streams, see bug 1501734
    if "--enable-streams" in flags:
        required.append("b8c1b5582913")  # m-c 440275 Fx64, 1st w/ working --enable-streams, see bug 1445854
    if "--wasm-gc" in flags:
        required.append("302befe7689a")  # m-c 413255 Fx61, 1st w/--wasm-gc, see bug 1445272
    if "--nursery-strings=on" in flags or "--nursery-strings=off" in flags:
        required.append("321c29f48508")  # m-c 406115 Fx60, 1st w/--nursery-strings=on, see bug 903519
    if platform.system() == "Windows" and options.buildWithClang:
        required.append("da5d7ba9a855")  # m-c 404087 Fx60, 1st w/ clang-cl.exe and MSVC 2017 builds, see bug 1402915
    if "--spectre-mitigations=on" in flags or "--spectre-mitigations=off" in flags:
        required.append("a98f615965d7")  # m-c 399868 Fx59, 1st w/--spectre-mitigations=on, see bug 1430053
    if "--test-wasm-await-tier2" in flags:
        required.append("b1dc87a94262")  # m-c 387188 Fx58, 1st w/--test-wasm-await-tier2, see bug 1388785
    if platform.system() == "Darwin":
        required.append("e2ecf684f49e")  # m-c 383101 Fx58, 1st w/ successful Xcode 9 builds, see bug 1366564
    if cpu_count_flag:
        required.append("1b55231e6628")  # m-c 380023 Fx57, 1st w/--cpu-count=<NUM>, see bug 1206770
    if platform.system() == "Windows" and platform.uname()[2] == "10":
        required.append("530f7bd28399")  # m-c 369571 Fx56, 1st w/ successful MSVC 2017 builds, see bug 1356493
    required.append("bb868860dfc3")  # m-c 330353 Fx53, 1st w/ revised template literals, see bug 1317375

    return f"first(({common_descendants(required)}) - ({skip_revs}))"


def common_descendants(revs):  # pylint: disable=missing-docstring,missing-return-doc,missing-return-type-doc
    return " and ".join(f"descendants({r})" for r in revs)

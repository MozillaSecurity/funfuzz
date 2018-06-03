# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Known broken changeset ranges of SpiderMonkey are specified in this file.
"""

from __future__ import absolute_import, unicode_literals  # isort:skip

import os
import platform
import sys

from pkg_resources import parse_version

if sys.version_info.major == 2 and os.name == "posix":
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess


def hgrange(first_bad, first_good):  # pylint: disable=missing-param-doc,missing-return-doc,missing-return-type-doc
    # pylint: disable=missing-type-doc
    """Like "first_bad::first_good", but includes branches/csets that never got the first_good fix."""
    # NB: mercurial's descendants(x) includes x
    # So this revset expression includes first_bad, but does not include first_good.
    # NB: hg log -r "(descendants(id(badddddd)) - descendants(id(baddddddd)))" happens to return the empty set,
    # like we want"
    return "(descendants(id(" + first_bad + "))-descendants(id(" + first_good + ")))"


def known_broken_ranges(options):  # pylint: disable=missing-param-doc,missing-return-doc,missing-return-type-doc
    # pylint: disable=missing-type-doc
    """Return a list of revsets corresponding to known-busted revisions."""
    # Paste numbers into: https://hg.mozilla.org/mozilla-central/rev/<number> to get hgweb link.
    # To add to the list:
    # - (1) will tell you when the brokenness started
    # - (1) python -m funfuzz.autobisectjs --compilationFailedLabel=bad -e FAILINGREV
    # - (2) will tell you when the brokenness ended
    # - (2) python -m funfuzz.autobisectjs --compilationFailedLabel=bad -s FAILINGREV

    # ANCIENT FIXME: It might make sense to avoid (or note) these in checkBlameParents.

    skips = [
        hgrange("7c25be97325d", "d426154dd31d"),  # Fx38, broken spidermonkey
        hgrange("da286f0f7a49", "62fecc6ab96e"),  # Fx39, broken spidermonkey
        hgrange("8a416fedec44", "7f9252925e26"),  # Fx41, broken spidermonkey
        hgrange("3bcc3881b95d", "c609df6d3895"),  # Fx44, broken spidermonkey
        hgrange("d3a026933bce", "5fa834fe9b96"),  # Fx52, broken spidermonkey
        hgrange("4c72627cfc6c", "926f80f2c5cc"),  # Fx60, broken spidermonkey
    ]

    if platform.system() == "Linux":
        skips.extend([
            # Clang failure - probably recent versions of GCC as well.
            hgrange("5232dd059c11", "ed98e1b9168d"),  # Fx41, see bug 1140482
            # Failure specific to GCC 5 (and probably earlier) - supposedly works on GCC 6
            hgrange("e94dceac8090", "516c01f62d84"),  # Fx56-57, see bug 1386011
        ])
        if not options.disableProfiling:
            skips.extend([
                # To bypass the following month-long breakage, use "--disable-profiling"
                hgrange("aa1da5ed8a07", "5a03382283ae"),  # Fx54-55, see bug 1339190
            ])

    if platform.system() == "Windows":
        skips.extend([
            hgrange("be8b0845f283", "db3ed1fdbbea"),  # Fx50, see bug 1289679
        ])

    if not options.enableDbg:
        skips.extend([
            hgrange("a048c55e1906", "ddaa87cfd7fa"),  # Fx46, broken opt builds w/ --enable-gczeal
            hgrange("c5561749c1c6", "f4c15a88c937"),  # Fx58-59, broken opt builds w/ --enable-gczeal
        ])

    if options.enableMoreDeterministic:
        skips.extend([
            hgrange("1d672188b8aa", "ea7dabcd215e"),  # Fx40, see bug 1149739
        ])

    if options.enableSimulatorArm32:
        skips.extend([
            hgrange("3a580b48d1ad", "20c9570b0734"),  # Fx43, broken 32-bit ARM-simulator builds
            hgrange("f35d1107fe2e", "bdf975ad2fcd"),  # Fx45, broken 32-bit ARM-simulator builds
            hgrange("6c37be9cee51", "4548ba932bde"),  # Fx50, broken 32-bit ARM-simulator builds
        ])

    return skips


def earliest_known_working_rev(options, flags, skip_revs):  # pylint: disable=missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc,too-many-branches,too-complex,too-many-statements
    """Return a revset which evaluates to the first revision of the shell that compiles with |options|
    and runs jsfunfuzz successfully with |flags|."""
    # Only support at least Mac OS X 10.11
    assert (not platform.system() == "Darwin") or (parse_version(platform.mac_ver()[0]) >= parse_version("10.11"))

    cpu_count_flag = False
    for entry in flags:  # flags is a list of flags, and the option must exactly match.
        if "--cpu-count=" in entry:
            cpu_count_flag = True

    required = []

    # These should be in descending order, or bisection will break at earlier changesets.
    if "--wasm-gc" in flags:
        required.append("302befe7689a")  # m-c 413255 Fx61, 1st w/--wasm-gc, see bug 1445272
    if "--nursery-strings=on" in flags or "--nursery-strings=off" in flags:
        required.append("321c29f48508")  # m-c 406115 Fx60, 1st w/--nursery-strings=on, see bug 903519
    if "--spectre-mitigations=on" in flags or "--spectre-mitigations=off" in flags:
        required.append("a98f615965d7")  # m-c 399868 Fx59, 1st w/--spectre-mitigations=on, see bug 1430053
    if "--test-wasm-await-tier2" in flags:
        required.append("b1dc87a94262")  # m-c 387188 Fx58, 1st w/--test-wasm-await-tier2, see bug 1388785
    if platform.system() == "Darwin":
        required.append("e2ecf684f49e")  # m-c 383101 Fx58, 1st w/ successful Xcode 9 builds, see bug 1366564
    if cpu_count_flag:
        required.append("1b55231e6628")  # m-c 380023 Fx57, 1st w/--cpu-count=<NUM>, see bug 1206770
    if "--no-wasm-ion" in flags:
        required.append("158b333a0a89")  # m-c 375650 Fx57, 1st w/--no-wasm-ion, see bug 1277562
    if "--no-wasm-baseline" in flags:
        required.append("9ea44ef0c07c")  # m-c 375639 Fx57, 1st w/--no-wasm-baseline, see bug 1277562
    if "--enable-streams" in flags:
        required.append("64bbc26920aa")  # m-c 371894 Fx56, 1st w/--enable-streams, see bug 1272697
    if platform.system() == "Windows" and platform.uname()[2] == "10":
        required.append("530f7bd28399")  # m-c 369571 Fx56, 1st w/ successful MSVC 2017 builds, see bug 1356493
    # Note that the sed version check only works with GNU sed, not BSD sed found in macOS.
    if (platform.system() == "Linux" and
            parse_version(subprocess.run(["sed", "--version"],
                                         stdout=subprocess.PIPE).stdout.decode("utf-8", errors="replace").split()[3])
            >= parse_version("4.3")):
        required.append("ebcbf47a83e7")  # m-c 328765 Fx53, 1st w/ working builds using sed 4.3+ found on Ubuntu 17.04+
    if options.disableProfiling:
        required.append("800a887c705e")  # m-c 324836 Fx53, 1st w/ --disable-profiling, see bug 1321065
    if "--no-wasm" in flags:
        required.append("e9b561d60697")  # m-c 321230 Fx52, 1st w/--no-wasm, see bug 1313180
    if "--cache-ir-stubs=on" in flags or "--cache-ir-stubs=off" in flags:
        required.append("1c5b92144e1e")  # m-c 308931 Fx51, 1st w/--cache-ir-stubs=on, see bug 1292659
    if "--ion-pgo=on" in flags or "--ion-pgo=off" in flags:
        required.append("b0a0ff5fa705")  # m-c 272274 Fx45, 1st w/--ion-pgo=on, see bug 1209515
    if options.buildWithAsan:
        required.append("d4e0e0e5d26d")  # m-c 268534 Fx44, 1st w/ reliable ASan builds w/ ICU, see bug 1214464
    if "--ion-sincos=on" in flags or "--ion-sincos=off" in flags:
        required.append("3dec2b935295")  # m-c 262544 Fx43, 1st w/--ion-sincos=on, see bug 984018
    if "--ion-instruction-reordering=on" in flags or "--ion-instruction-reordering=off" in flags:
        required.append("59d2f2e62420")  # m-c 259672 Fx43, 1st w/--ion-instruction-reordering=on, see bug 1195545
    if "--ion-shared-stubs=on" in flags or "--ion-shared-stubs=off" in flags:
        required.append("3655d19ce241")  # m-c 257573 Fx43, 1st w/--ion-shared-stubs=on, see bug 1168756
    if options.enableSimulatorArm32 or options.enableSimulatorArm64:
        # For ARM64: This should get updated whenever ARM64 builds are stable
        required.append("25e99bc12482")  # m-c 249239 Fx41, 1st w/--enable-simulator=[arm|arm64|mips], see bug 1173992
    if "--ion-regalloc=testbed" in flags:
        required.append("47e92bae09fd")  # m-c 248962 Fx41, 1st w/--ion-regalloc=testbed, see bug 1170840
    if "--execute=setJitCompilerOption(\"ion.forceinlineCaches\",1)" in flags:
        required.append("ea9608e33abe")  # m-c 247709 Fx41, 1st w/ion.forceinlineCaches, see bug 923717
    if "--no-unboxed-objects" in flags:
        required.append("322487136b28")  # m-c 244297 Fx41, 1st w/--no-unboxed-objects, see bug 1162199
    if "--ion-extra-checks" in flags:
        required.append("cdf93416b39a")  # m-c 234228 Fx39, 1st w/--ion-extra-checks, see bug 1139152
    if "--no-cgc" in flags:
        required.append("b63d7e80709a")  # m-c 227705 Fx38, 1st w/--no-cgc, see bug 1126769 and see bug 1129233
    if "--enable-avx" in flags or "--no-avx" in flags:
        required.append("5e6e959f0043")  # m-c 223959 Fx38, 1st w/--enable-avx, see bug 1118235
    required.append("bcacb5692ad9")  # m-c 222786 Fx37, 1st w/ successful GCC 5.2.x builds on Ubuntu 15.10 onwards

    return "first((" + common_descendants(required) + ") - (" + skip_revs + "))"


def common_descendants(revs):  # pylint: disable=missing-docstring,missing-return-doc,missing-return-type-doc
    return " and ".join("descendants(" + r + ")" for r in revs)

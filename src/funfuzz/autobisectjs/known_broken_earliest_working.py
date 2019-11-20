# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Known broken changeset ranges of SpiderMonkey are specified in this file.
"""

import platform
import subprocess

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
        # Fx60, broken spidermonkey
        hgrange("4c72627cfc6c2dafb4590637fe1f3b5a24e133a4", "926f80f2c5ccaa5b0374b48678d62c304cbc9a68"),
        # Fx63, broken spidermonkey
        hgrange("1fb7ddfad86d5e085c4f2af23a2519d37e45a3e4", "5202cfbf8d60ffbb1ad9c385eda725992fc43d7f"),
        # Fx64, broken spidermonkey
        hgrange("aae4f349fa588aa844cfb14fae278b776aed6cb7", "c5fbbf959e23a4f33d450cb6c64ef739e09fbe13"),
        # Fx66, broken spidermonkey
        hgrange("f611bc50d11cae1f48cc44d1468f2c34ec46e287", "39d0c50a2209e0f0c982b1d121765c9dc950e161"),
        # Fx69, broken spidermonkey
        hgrange("1e4c1b283ba3e4260e1f52bd3b4cba8805bc28b9", "7fd7b5ac5743c0b219fc823441e09d84143f306a"),
        # Fx69, broken spidermonkey
        hgrange("36ceb8f15cb9fd797cced7f4f37c2691916b72d5", "25663e783e96b0c1a879685c295955fa2eaaf8d8"),
    ]

    if platform.system() == "Darwin":
        skips.extend([
            # Fx68, see bug 1544418
            hgrange("3d0236f985f83c6b2f4800f814c004e0a2902468", "32cef42080b1f7443dfe767652ea44e0dafbfd9c"),
        ])

    if platform.system() == "Linux":
        skips.extend([
            # Fx56-57, failure specific to GCC 5 (and probably earlier) - supposedly works on GCC 6, see bug 1386011
            hgrange("e94dceac80907abd4b579ddc8b7c202bbf461ec7", "516c01f62d840744648768b6fac23feb770ffdc1"),
        ])
        if platform.machine() == "aarch64":
            skips.extend([
                # Fx54, see bug 1336344
                hgrange("e8bb22053e65e2a82456e9243a07af023a8ebb13", "999757e9e5a576c884201746546a3420a92f7447"),
            ])
        if not options.disableProfiling:
            skips.extend([
                # Fx54-55, to bypass the following month-long breakage, use "--disable-profiling", see bug 1339190
                hgrange("aa1da5ed8a0719e0ab424e672d2f477b70ef593c", "5a03382283ae0a020b2a2d84bbbc91ff13cb2130"),
            ])
        glibc_version = subprocess.run(["ldd", "--version"],
                                       check=True,
                                       encoding="utf-8",
                                       stdout=subprocess.PIPE).stdout.splitlines()[0].split()[-1]
        if parse_version(glibc_version) >= parse_version("2.28"):
            skips.extend([
                # Fx62-67, to bypass this 9-month-long breakage, use Ubuntu 18.04 or glibc < 2.28, see bug 1533969
                # Or try and construct a one line patch to be applied during each compile
                hgrange("e8d4a24e47a943db327206a4680fb75c156f9086", "7b85bf9c5210e5679fa6cfad92466a6e2ba30232"),
            ])

    if not options.enableDbg:
        skips.extend([
            # Fx58-59, broken opt builds w/ --enable-gczeal
            hgrange("c5561749c1c64793c31699d46bbf12cc0c69815c", "f4c15a88c937e8b3940f5c1922142a6ffb137320"),
            # Fx66, broken opt builds w/ --enable-gczeal
            hgrange("247e265373eb26566e94303fa42b1237b80295d9", "e4aa68e2a85b027c5498bf8d8f379b06d07df6c2"),
        ])

    if options.enableMoreDeterministic:
        skips.extend([
            # Fx68, see bug 1542980
            hgrange("427b854cdb1c47ce6a643f83245914d66dca4382", "4c4e45853808229f832e32f6bcdbd4c92a72b13b"),
        ])

    if options.enableSimulatorArm32:
        skips.extend([
            # Fx57-61, broken 32-bit ARM-simulator builds
            hgrange("284002382c21842a7ebb39dcf53d5d34fd3f7692", "05669ce25b032bf83ca38e082e6f2c1bf683ed19"),
        ])

    return skips


def earliest_known_working_rev(_options, flags, skip_revs):  # pylint: disable=missing-param-doc,missing-return-doc
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
    if "--enable-weak-refs" in flags:  # 1st w/--enable-weak-refs, see bug 1587098
        required.append("f273ec2ec0aecce1938a78f01925764d02af2ad2")  # m-c 500139 Fx72
    if platform.system() == "Windows":  # 1st w/ working Windows builds w/a recent Win10 SDK and Rust 1.38+
        required.append("fbcb7dcd82acfc9196c0dfd60e28248c25a4583b")  # m-c 497927 Fx71
    # Note that m-c rev 481620:2e490776b07e35013ae07a47798a983f482ffaa3 is the first with blinterp in-tree test fixes
    if set(["--blinterp-eager", "--no-blinterp",
            "--blinterp"]).intersection(flags):  # 1st w/--blinterp-eager,--no-blinterp,--blinterp, see bug 1562129
        required.append("2e490776b07e35013ae07a47798a983f482ffaa3")  # m-c 481620 Fx69
    if "--enable-experimental-fields" in flags:  # 1st w/--enable-experimental-fields, see bug 1529758
        required.append("7a1ad6647c22bd34a6c70e67dc26e5b83f71cea4")  # m-c 463705 Fx67
    # Note that m-c rev 457581:4b74d76e55a819852c8fa925efd25c57fdf35c9d is the first with BigInt on by default
    if set(["--wasm-compiler=none", "--wasm-compiler=baseline+ion", "--wasm-compiler=baseline", "--wasm-compiler=ion",
            "--wasm-compiler=cranelift"]).intersection(flags):  # 1st w/--wasm-compiler=none/<others>, see bug 1509441
        required.append("48dc14f79fb0a51ca796257a4179fe6f16b71b14")  # m-c 455252 Fx66
    if "--more-compartments" in flags:  # 1st w/--more-compartments, see bug 1518753
        required.append("450b8f0cbb4e494b399ebcf23a33b8d9cb883245")  # m-c 453627 Fx66
    if "--no-streams" in flags:  # 1st w/ working --no-streams, see bug 1501734
        required.append("c6a8b4d451afa922c4838bd202749c7e131cf05e")  # m-c 442977 Fx65
    if platform.system() == "Darwin":  # 1st w/ successful Xcode 10.3 builds, see bug 1270217
        required.append("6b7ace4745e30ba914ea8350bfc7fa12f2980c54")  # m-c 420996 Fx62
    if "--wasm-gc" in flags:  # 1st w/--wasm-gc, see bug 1445272
        required.append("302befe7689abad94a75f66ded82d5e71b558dc4")  # m-c 413255 Fx61
    if "--nursery-strings=on" in flags or \
            "--nursery-strings=off" in flags:  # 1st w/--nursery-strings=on, see bug 903519
        required.append("321c29f4850882a2f0220a4dc041c53992c47992")  # m-c 406115 Fx60
    if "--spectre-mitigations=on" in flags or \
            "--spectre-mitigations=off" in flags:  # 1st w/--spectre-mitigations=on, see bug 1430053
        required.append("a98f615965d73f6462924188fc2b1f2a620337bb")  # m-c 399868 Fx59
    if "--test-wasm-await-tier2" in flags:  # 1st w/--test-wasm-await-tier2, see bug 1388785
        required.append("b1dc87a94262c1bf2747d2bf560e21af5deb3174")  # m-c 387188 Fx58
    if cpu_count_flag:  # 1st w/--cpu-count=<NUM>, see bug 1206770
        required.append("1b55231e6628e70f0c2ee2b2cb40a1e9861ac4b4")  # m-c 380023 Fx57
    # 1st w/ revised template literals, see bug 1317375
    required.append("bb868860dfc35876d2d9c421c037c75a4fb9b3d2")  # m-c 330353 Fx53

    return f"first(({common_descendants(required)}) - ({skip_revs}))"


def common_descendants(revs):  # pylint: disable=missing-docstring,missing-return-doc,missing-return-type-doc
    return " and ".join(f"descendants({r})" for r in revs)

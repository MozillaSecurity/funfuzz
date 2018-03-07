# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Allows detection of support for various command-line flags.
"""

from __future__ import absolute_import, print_function

import multiprocessing
import random
import sys

from past.builtins import range  # pylint: disable=redefined-builtin

from . import inspect_shell

if sys.version_info.major == 2:
    from functools32 import lru_cache  # pylint: disable=import-error
else:
    from functools import lru_cache  # pylint: disable=no-name-in-module


@lru_cache(maxsize=None)
def shellSupportsFlag(shellPath, flag):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc
    # pylint: disable=missing-return-type-doc
    return inspect_shell.shellSupports(shellPath, [flag, '-e', '42'])


def chance(p):  # pylint: disable=invalid-name,missing-docstring,missing-return-doc,missing-return-type-doc
    return random.random() < p


def randomFlagSet(shellPath):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc,too-complex,too-many-branches,too-many-statements
    """Return a random list of CLI flags appropriate for the given shell.

    Only works for spidermonkey js shell. Does not work for xpcshell.
    """
    args = []

    ion = shellSupportsFlag(shellPath, "--ion") and chance(.8)

    if shellSupportsFlag(shellPath, '--fuzzing-safe'):
        args.append("--fuzzing-safe")  # --fuzzing-safe landed in bug 885361

    # Landed in m-c changeset 399868:a98f615965d7, see bug 1430053
    if shellSupportsFlag(shellPath, "--spectre-mitigations=on") and chance(.3):
        args.append("--spectre-mitigations=on" if chance(.9) else "--spectre-mitigations=off")

    # Landed in m-c changeset c0c1d923c292, see bug 1255008
    if shellSupportsFlag(shellPath, '--ion-aa=flow-sensitive'):
        if chance(.4):
            args.append('--ion-aa=flow-sensitive')
        elif shellSupportsFlag(shellPath, '--ion-aa=flow-insensitive') and chance(.4):
            args.append('--ion-aa=flow-insensitive')

    # Note for future: --wasm-check-bce is only useful for x86 and ARM32

    if shellSupportsFlag(shellPath, '--wasm-always-baseline') and chance(.5):
        args.append("--wasm-always-baseline")  # --wasm-always-baseline landed in bug 1232205

    if shellSupportsFlag(shellPath, '--ion-pgo=on') and chance(.2):
        args.append("--ion-pgo=on")  # --ion-pgo=on landed in bug 1209515

    if shellSupportsFlag(shellPath, '--ion-sincos=on') and chance(.5):
        sincos_switch = "on" if chance(0.5) else "off"
        args.append("--ion-sincos=" + sincos_switch)  # --ion-sincos=[on|off] landed in bug 984018

    if shellSupportsFlag(shellPath, '--ion-instruction-reordering=on') and chance(.2):
        args.append("--ion-instruction-reordering=on")  # --ion-instruction-reordering=on landed in bug 1195545

    if shellSupportsFlag(shellPath, '--ion-shared-stubs=on') and chance(.2):
        args.append("--ion-shared-stubs=on")  # --ion-shared-stubs=on landed in bug 1168756

    if shellSupportsFlag(shellPath, '--non-writable-jitcode') and chance(.3):
        args.append("--non-writable-jitcode")  # --non-writable-jitcode landed in bug 977805

    if shellSupportsFlag(shellPath, "--execute=setJitCompilerOption('ion.forceinlineCaches',1)") and chance(.1):
        args.append("--execute=setJitCompilerOption('ion.forceinlineCaches',1)")

    if shellSupportsFlag(shellPath, '--no-cgc') and chance(.1):
        args.append("--no-cgc")  # --no-cgc landed in bug 1126769

    if shellSupportsFlag(shellPath, '--no-ggc') and chance(.1):
        args.append("--no-ggc")  # --no-ggc landed in bug 706885

    if shellSupportsFlag(shellPath, '--no-incremental-gc') and chance(.1):
        args.append("--no-incremental-gc")  # --no-incremental-gc landed in bug 958492

    if shellSupportsFlag(shellPath, '--no-unboxed-objects') and chance(.2):
        args.append("--no-unboxed-objects")  # --no-unboxed-objects landed in bug 1162199

    # if shellSupportsFlag(shellPath, '--ion-sink=on') and chance(.2):
    #    args.append("--ion-sink=on")  # --ion-sink=on landed in bug 1093674

    if shellSupportsFlag(shellPath, '--gc-zeal=0') and chance(.9):
        # Focus testing on CheckNursery (16), see:
        #     https://hg.mozilla.org/mozilla-central/rev/bdbb5822afe1
        gczeal_value = 16 if chance(0.5) else random.randint(0, 16)
        args.append("--gc-zeal=" + str(gczeal_value))  # --gc-zeal= landed in bug 1101602

    if shellSupportsFlag(shellPath, '--enable-small-chunk-size') and chance(.1):
        args.append("--enable-small-chunk-size")  # --enable-small-chunk-size landed in bug 941804

    if shellSupportsFlag(shellPath, '--ion-loop-unrolling=on') and chance(.2):
        args.append("--ion-loop-unrolling=on")  # --ion-loop-unrolling=on landed in bug 1039458

    if shellSupportsFlag(shellPath, '--no-threads') and chance(.5):
        args.append("--no-threads")  # --no-threads landed in bug 1031529

    if shellSupportsFlag(shellPath, '--disable-ion') and chance(.05):
        args.append("--disable-ion")  # --disable-ion landed in bug 789319

    if shellSupportsFlag(shellPath, '--no-native-regexp') and chance(.1):
        args.append("--no-native-regexp")  # See bug 976446

    if inspect_shell.queryBuildConfiguration(shellPath, 'arm-simulator') and chance(.4):
        args.append('--arm-sim-icache-checks')

    if (shellSupportsFlag(shellPath, '--no-sse3') and shellSupportsFlag(shellPath, '--no-sse4')) and chance(.2):
        # --no-sse3 and --no-sse4 landed in m-c rev 526ba3ace37a.
        if chance(.5):
            args.append("--no-sse3")
        else:
            args.append("--no-sse4")

    if shellSupportsFlag(shellPath, '--no-asmjs') and chance(.5):
        args.append("--no-asmjs")

    # --baseline-eager landed after --no-baseline on the IonMonkey branch prior to landing on m-c.
    if shellSupportsFlag(shellPath, '--baseline-eager'):
        if chance(.3):
            args.append('--no-baseline')
        # elif is important, as we want to call --baseline-eager only if --no-baseline is not set.
        elif chance(.6):
            args.append("--baseline-eager")

    # Landed in m-c changeset 380023:1b55231e6628, see bug 1206770
    if shellSupportsFlag(shellPath, "--cpu-count=1"):
        if chance(.7):
            # Focus on the reproducible cases
            args.append("--ion-offthread-compile=off")
        elif chance(.5) and multiprocessing.cpu_count() > 1 and shellSupportsFlag(shellPath, "--cpu-count=1"):
            # Adjusts default number of threads for parallel compilation (turned on by default)
            total_threads = random.randint(2, (multiprocessing.cpu_count() * 2))
            args.append("--cpu-count=" + str(total_threads))

    if ion:
        if chance(.6):
            args.append("--ion-eager")
        if chance(.2):
            args.append("--ion-gvn=off")
        if chance(.2):
            args.append("--ion-licm=off")
        if shellSupportsFlag(shellPath, '--ion-edgecase-analysis=off') and chance(.2):
            args.append("--ion-edgecase-analysis=off")
        if chance(.2):
            args.append("--ion-range-analysis=off")
        if chance(.2):
            args.append("--ion-inlining=off")
        if chance(.2):
            args.append("--ion-osr=off")
        if chance(.2):
            args.append("--ion-limit-script-size=off")
        # Backtracking (on by default as of 2015-04-15) and stupid landed in m-c changeset dc4887f61d2e
        # The stupid allocator isn't used by default and devs prefer not to have to fix fuzzbugs
        # if shellSupportsFlag(shellPath, '--ion-regalloc=stupid') and chance(.2):
            # args.append('--ion-regalloc=stupid')
        if shellSupportsFlag(shellPath, '--ion-regalloc=testbed') and chance(.2):
            args.append('--ion-regalloc=testbed')
        if shellSupportsFlag(shellPath, '--ion-check-range-analysis') and chance(.3):
            args.append('--ion-check-range-analysis')
        if shellSupportsFlag(shellPath, '--ion-extra-checks') and chance(.3):
            args.append('--ion-extra-checks')
    else:
        args.append("--no-ion")

    # if chance(.05):
    #    args.append("--execute=verifyprebarriers()")

    if chance(.05):
        args.append("-D")  # aka --dump-bytecode

    return args


def basic_flag_sets(shell_path):
    """These flag combos are used w/the original flag sets when run through Lithium & autoBisect.

    Args:
        shell_path (str): Path to shell.

    Returns:
        list: Possible shell runtime flag combinations for fuzzing.
    """
    basic_flags = [
        # Parts of this flag permutation come from:
        # https://hg.mozilla.org/mozilla-central/file/c91249f41e37/js/src/tests/lib/tests.py#l13
        # compare_jit uses the following first flag set as the sole baseline when fuzzing
        ["--fuzzing-safe", "--no-threads", "--ion-eager"],
        ["--fuzzing-safe"],
        ["--fuzzing-safe", "--ion-offthread-compile=off", "--ion-eager"],
        ["--fuzzing-safe", "--ion-offthread-compile=off"],
        ["--fuzzing-safe", "--baseline-eager"],
        ["--fuzzing-safe", "--no-baseline", "--no-ion"],
    ]
    if shellSupportsFlag(shell_path, "--non-writable-jitcode"):
        basic_flags.append(["--fuzzing-safe", "--no-threads", "--ion-eager",
                            "--non-writable-jitcode", "--ion-check-range-analysis",
                            "--ion-extra-checks", "--no-sse3"])
    if shellSupportsFlag(shell_path, "--no-wasm"):
        basic_flags.append(["--fuzzing-safe", "--no-baseline", "--no-asmjs",
                            "--no-wasm", "--no-native-regexp"])
    if shellSupportsFlag(shell_path, "--wasm-always-baseline"):
        basic_flags.append(["--fuzzing-safe", "--no-threads", "--ion-eager",
                            "--wasm-always-baseline"])
    return basic_flags


# Consider adding a function (for compare_jit reduction) that takes a flag set
# and returns all its (meaningful) subsets.


def testRandomFlags():  # pylint: disable=invalid-name,missing-docstring
    for _ in range(100):
        print(" ".join(randomFlagSet(sys.argv[1])))


if __name__ == "__main__":
    testRandomFlags()

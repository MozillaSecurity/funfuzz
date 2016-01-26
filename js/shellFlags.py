import multiprocessing
import os
import random
import sys

import inspectShell

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
import subprocesses as sps

def memoize(f, cache={}):
    '''Function decorator that caches function results.'''
    # From http://code.activestate.com/recipes/325205-cache-decorator-in-python-24/#c9
    def g(*args, **kwargs):
        key = (f, tuple(args), frozenset(kwargs.items()))
        if key not in cache:
            cache[key] = f(*args, **kwargs)
        return cache[key]
    return g


@memoize
def shellSupportsFlag(shellPath, flag):
    return inspectShell.shellSupports(shellPath, [flag, '-e', '42'])


def chance(p):
    return random.random() < p


def randomFlagSet(shellPath):
    '''
    Returns a random list of command-line flags appropriate for the given shell.
    Only works for spidermonkey js shell. Does not work for xpcshell.
    '''

    args = []

    ion = shellSupportsFlag(shellPath, "--ion") and chance(.8)

    if shellSupportsFlag(shellPath, '--fuzzing-safe'):
        args.append("--fuzzing-safe")  # --fuzzing-safe landed in bug 885361

    # See bug 932517, which had landed to fix this issue. Keeping this around for archives:
    #   Original breakage in m-c rev 269359 : https://hg.mozilla.org/mozilla-central/rev/a0ccab2a6e28
    #   Fix in m-c rev 269896: https://hg.mozilla.org/mozilla-central/rev/3bb8446a6d8d
    # Anything in-between involving let probably needs "-e 'version(185);'" to see if we can bypass breakage
    # if shellSupportsFlag(shellPath, "--execute='version(185);'"):
    #     args.append("--execute='version(185);'")

    if shellSupportsFlag(shellPath, '--ion-sincos=on') and chance(.5):
        sincosValue = "on" if chance(0.5) else "off"
        args.append("--ion-sincos=" + sincosValue)  # --ion-sincos=[on|off] landed in bug 984018

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

    #if shellSupportsFlag(shellPath, '--ion-sink=on') and chance(.2):
    #    args.append("--ion-sink=on")  # --ion-sink=on landed in bug 1093674

    if shellSupportsFlag(shellPath, '--gc-zeal=0') and chance(.9):
        gczealValue = 14 if chance(0.5) else random.randint(0, 14)  # Focus test compacting GC (14)
        args.append("--gc-zeal=" + str(gczealValue))  # --gc-zeal= landed in bug 1101602

    if shellSupportsFlag(shellPath, '--enable-small-chunk-size') and chance(.1):
        args.append("--enable-small-chunk-size")  # --enable-small-chunk-size landed in bug 941804

    if shellSupportsFlag(shellPath, '--ion-loop-unrolling=on') and chance(.2):
        args.append("--ion-loop-unrolling=on")  # --ion-loop-unrolling=on landed in bug 1039458

    if shellSupportsFlag(shellPath, '--no-threads') and chance(.5):
        args.append("--no-threads")  # --no-threads landed in bug 1031529

    if shellSupportsFlag(shellPath, '--disable-ion') and chance(.05):
        args.append("--disable-ion")  # --disable-ion landed in bug 789319

    # See bug 1026919 comment 60:
    if sps.isARMv7l and \
            shellSupportsFlag(shellPath, '--arm-asm-nop-fill=0') and chance(0.3):
        # It was suggested to focus more on the range between 0 and 1.
        # Reduced the upper limit to 8, see bug 1053996 comment 8.
        asmNopFill = random.randint(1, 8) if chance(0.3) else random.randint(0, 1)
        args.append("--arm-asm-nop-fill=" + str(asmNopFill))  # Landed in bug 1020834

    # See bug 1026919 comment 60:
    if sps.isARMv7l and \
            shellSupportsFlag(shellPath, '--asm-pool-max-offset=1024') and chance(0.3):
        asmPoolMaxOffset = random.randint(5, 1024)
        args.append("--asm-pool-max-offset=" + str(asmPoolMaxOffset))  # Landed in bug 1026919

    if shellSupportsFlag(shellPath, '--no-native-regexp') and chance(.1):
        args.append("--no-native-regexp")  # See bug 976446

    if inspectShell.queryBuildConfiguration(shellPath, 'arm-simulator') and chance(.4):
        args.append('--arm-sim-icache-checks')

    if (shellSupportsFlag(shellPath, '--no-sse3') and shellSupportsFlag(shellPath, '--no-sse4')) and chance(.2):
        # --no-sse3 and --no-sse4 landed in m-c rev 526ba3ace37a.
        if chance(.5):
            args.append("--no-sse3")
        else:
            args.append("--no-sse4")

    if shellSupportsFlag(shellPath, '--no-fpu') and chance(.2):
        args.append("--no-fpu")  # --no-fpu landed in bug 858022

    if shellSupportsFlag(shellPath, '--no-asmjs') and chance(.5):
        args.append("--no-asmjs")

    # --baseline-eager landed after --no-baseline on the IonMonkey branch prior to landing on m-c.
    if shellSupportsFlag(shellPath, '--baseline-eager'):
        if chance(.3):
            args.append('--no-baseline')
        # elif is important, as we want to call --baseline-eager only if --no-baseline is not set.
        elif chance(.6):
            args.append("--baseline-eager")

    if shellSupportsFlag(shellPath, '--ion-offthread-compile=off'):
        if chance(.7):
            # Focus on the reproducible cases
            args.append("--ion-offthread-compile=off")
        elif chance(.5) and multiprocessing.cpu_count() > 1 and \
                shellSupportsFlag(shellPath, '--thread-count=1'):
            # Adjusts default number of threads for parallel compilation (turned on by default)
            totalThreads = random.randint(2, (multiprocessing.cpu_count() * 2))
            args.append('--thread-count=' + str(totalThreads))
        # else:
        #   Default is to have --ion-offthread-compile=on and --thread-count=<some default value>
    elif shellSupportsFlag(shellPath, '--ion-parallel-compile=off'):
        # --ion-parallel-compile=off has gone away as of m-c rev 9ab3b097f304 and f0d67b1ccff9.
        if chance(.7):
            # Focus on the reproducible cases
            args.append("--ion-parallel-compile=off")
        elif chance(.5) and multiprocessing.cpu_count() > 1 and \
                shellSupportsFlag(shellPath, '--thread-count=1'):
            # Adjusts default number of threads for parallel compilation (turned on by default)
            totalThreads = random.randint(2, (multiprocessing.cpu_count() * 2))
            args.append('--thread-count=' + str(totalThreads))
        # else:
        #   The default is to have --ion-parallel-compile=on and --thread-count=<some default value>

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
        #if shellSupportsFlag(shellPath, '--ion-regalloc=stupid') and chance(.2):
            #args.append('--ion-regalloc=stupid')
        if shellSupportsFlag(shellPath, '--ion-regalloc=testbed') and chance(.2):
            args.append('--ion-regalloc=testbed')
        if shellSupportsFlag(shellPath, '--ion-check-range-analysis'):
            if chance(.3):
                args.append('--ion-check-range-analysis')
        if shellSupportsFlag(shellPath, '--ion-extra-checks'):
            if chance(.3):
                args.append('--ion-extra-checks')
    else:
        args.append("--no-ion")

    #if chance(.05):
    #    args.append("--execute=verifyprebarriers()")

    if chance(.05):
        args.append("-D")  # aka --dump-bytecode

    return args


def basicFlagSets(shellPath):
    '''
    compareJIT uses these combinations of flags (as well as the original set of flags) when run
    through Lithium and autoBisect.
    '''
    if shellSupportsFlag(shellPath, "--no-threads"):
        basicFlagList = [
            # Parts of this flag permutation come from:
            # https://hg.mozilla.org/mozilla-central/file/e3bf27190360/js/src/tests/lib/tests.py#l12
            ['--fuzzing-safe', '--no-threads', '--ion-eager'],  # compareJIT uses this first flag set as the sole baseline when fuzzing
            ['--fuzzing-safe', '--ion-offthread-compile=off', '--ion-eager'],
            ['--fuzzing-safe', '--ion-offthread-compile=off', '--baseline-eager'],
            ['--fuzzing-safe', '--no-threads', '--baseline-eager'],
            # Temporarily disabled due to lots of mismatch on stdout spew:
            # ['--fuzzing-safe', '--no-threads', '--baseline-eager', '--no-fpu'],
            ['--fuzzing-safe', '--no-threads', '--no-baseline', '--no-ion'],
            ['--fuzzing-safe', '--no-threads', '--no-ion'],  # See bug 1203862
        ]
        if shellSupportsFlag(shellPath, "--non-writable-jitcode"):
            basicFlagList.append(['--fuzzing-safe', '--no-threads', '--ion-eager',
                                  '--non-writable-jitcode', '--ion-check-range-analysis',
                                  '--ion-extra-checks', '--no-sse3'])
        return basicFlagList
    elif shellSupportsFlag(shellPath, "--ion-offthread-compile=off"):
        basicFlagList = [
            # Parts of this flag permutation come from:
            # https://hg.mozilla.org/mozilla-central/file/84bd8d9f4256/js/src/tests/lib/tests.py#l12
            # as well as other interesting flag combinations that have found / may find new bugs.
            ['--fuzzing-safe', '--ion-offthread-compile=off'],  # compareJIT uses this first flag set as the sole baseline when fuzzing
            ['--fuzzing-safe', '--ion-offthread-compile=off', '--no-baseline'],  # Not in jit_test.py though...
            ['--fuzzing-safe', '--ion-offthread-compile=off', '--no-baseline', '--no-ion'],
            ['--fuzzing-safe', '--ion-offthread-compile=off', '--no-baseline', '--ion-eager'],  # Not in jit_test.py though...
            ['--fuzzing-safe', '--ion-offthread-compile=off', '--ion-eager'],  # Not in jit_test.py though...
            ['--fuzzing-safe', '--ion-offthread-compile=off', '--no-ion'],  # Not in jit_test.py though, see bug 848906 comment 1
            # Temporarily disabled due to lots of mismatch on stdout spew:
            # ['--fuzzing-safe', '--ion-offthread-compile=off', '--no-fpu'],
        ]
        if shellSupportsFlag(shellPath, "--thread-count=1"):
            basicFlagList.append(['--fuzzing-safe', '--ion-offthread-compile=off', '--ion-eager'])
            # Range analysis had only started to stabilize around the time when --no-sse3 landed.
            if shellSupportsFlag(shellPath, '--no-sse3'):
                basicFlagList.append(['--fuzzing-safe', '--ion-offthread-compile=off',
                                      '--ion-eager', '--ion-check-range-analysis', '--no-sse3'])
        return basicFlagList
    else:
        basicFlagList = [
            # Parts of this flag permutation come from:
            # https://hg.mozilla.org/mozilla-central/file/10932f3a0ba0/js/src/tests/lib/tests.py#l12
            # as well as other interesting flag combinations that have found / may find new bugs.
            ['--fuzzing-safe', '--ion-parallel-compile=off'],  # compareJIT uses this first flag set as the sole baseline when fuzzing
            ['--fuzzing-safe', '--ion-parallel-compile=off', '--no-baseline'],  # Not in jit_test.py though...
            ['--fuzzing-safe', '--ion-parallel-compile=off', '--no-baseline', '--no-ion'],
            ['--fuzzing-safe', '--ion-parallel-compile=off', '--no-baseline', '--ion-eager'],  # Not in jit_test.py though...
            ['--fuzzing-safe', '--ion-parallel-compile=off', '--ion-eager'],  # Not in jit_test.py though...
            ['--fuzzing-safe', '--ion-parallel-compile=off', '--baseline-eager'],
            ['--fuzzing-safe', '--ion-parallel-compile=off', '--baseline-eager', '--no-ion'],  # See bug 848906 comment 1
            # Temporarily disabled due to lots of mismatch on stdout spew:
            # ['--fuzzing-safe', '--ion-parallel-compile=off', '--baseline-eager', '--no-fpu'],
        ]
        if shellSupportsFlag(shellPath, "--thread-count=1"):
            basicFlagList.append(['--fuzzing-safe', '--ion-eager', '--ion-parallel-compile=off'])
            # Range analysis had only started to stabilize around the time when --no-sse3 landed.
            if shellSupportsFlag(shellPath, '--no-sse3'):
                basicFlagList.append(['--fuzzing-safe', '--ion-parallel-compile=off',
                                      '--ion-eager', '--ion-check-range-analysis', '--no-sse3'])
        return basicFlagList


# Consider adding a function (for compareJIT reduction) that takes a flag set
# and returns all its (meaningful) subsets.


def testRandomFlags():
    for _ in range(100):
        print ' '.join(randomFlagSet(sys.argv[1]))


if __name__ == "__main__":
    testRandomFlags()

import random
from multiprocessing import cpu_count

from inspectShell import queryBuildConfiguration, shellSupports, testBinary

def memoize(f, cache={}):
    '''Function decorator that caches function results.'''
    # From http://code.activestate.com/recipes/325205-cache-decorator-in-python-24/#c9
    def g(*args, **kwargs):
        key = ( f, tuple(args), frozenset(kwargs.items()) )
        if key not in cache:
            cache[key] = f(*args, **kwargs)
        return cache[key]
    return g


@memoize
def shellSupportsFlag(shellPath, flag):
    return shellSupports(shellPath, [flag, '-e', '42'])


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

    if shellSupportsFlag(shellPath, '--no-native-regexp') and chance(.1):
        args.append("--no-native-regexp")  # See bug 976446

    if shellSupportsFlag(shellPath, '--latin1-strings') and chance(.2):
        args.append("--latin1-strings")  # See bug 1028867

    if queryBuildConfiguration(shellPath, 'arm-simulator') and chance(.4):
        args.append('--arm-sim-icache-checks')

    if (shellSupportsFlag(shellPath, '--no-sse3') and shellSupportsFlag(shellPath, '--no-sse4')) \
            and chance(.2):
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
        elif chance(.5) and cpu_count() > 1 and shellSupportsFlag(shellPath, '--thread-count=1'):
            # Adjusts default number of threads for parallel compilation (turned on by default)
            totalThreads = random.randint(2, (cpu_count() * 2))
            args.append('--thread-count=' + str(totalThreads))
        # else:
        #   Default is to have --ion-offthread-compile=on and --thread-count=<some default value>
    elif shellSupportsFlag(shellPath, '--ion-parallel-compile=off'):
        # --ion-parallel-compile=off has gone away as of m-c rev 9ab3b097f304 and f0d67b1ccff9.
        if chance(.7):
            # Focus on the reproducible cases
            args.append("--ion-parallel-compile=off")
        elif chance(.5) and cpu_count() > 1 and shellSupportsFlag(shellPath, '--thread-count=1'):
            # Adjusts default number of threads for parallel compilation (turned on by default)
            totalThreads = random.randint(2, (cpu_count() * 2))
            args.append('--thread-count=' + str(totalThreads))
        # else:
        #   The default is to have --ion-parallel-compile=on and --thread-count=<some default value>

    if ion:
        if chance(.6):
            args.append("--ion-eager")
        if chance(.2):
            args.append("--ion-gvn=" + random.choice(["off", "pessimistic", "optimistic"]))
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
        # Landed in m-c changeset 8db8eef79b8c
        if shellSupportsFlag(shellPath, '--ion-regalloc=lsra'):
            if chance(.1):
                args.append('--ion-regalloc=lsra')  # On by default
            # Backtracking and stupid landed in m-c changeset dc4887f61d2e
            elif shellSupportsFlag(shellPath, '--ion-regalloc=backtracking') and chance(.4):
                args.append('--ion-regalloc=backtracking')
            # Disabled until bug 871848 is fixed.
            #elif shellSupportsFlag(shellPath, '--ion-regalloc=stupid') and chance(.2):
            #    args.append('--ion-regalloc=stupid')
        if shellSupportsFlag(shellPath, '--ion-check-range-analysis'):
            if chance(.5):
                args.append('--ion-check-range-analysis')
    else:
        args.append("--no-ion")

    #if chance(.05):
    #    args.append("--execute=verifyprebarriers()")
    #if chance(.05):
    #    args.append("--execute=verifypostbarriers()")

    if chance(.05):
        args.append("-D") # aka --dump-bytecode

    return args


def basicFlagSets(shellPath):
    '''
    compareJIT uses these combinations of flags (as well as the original set of flags) when run
    through Lithium and autoBisect.
    '''
    if shellSupportsFlag(shellPath, "--ion-offthread-compile=off"):
        basicFlagList = [
            # Parts of this flag permutation come from:
            # https://hg.mozilla.org/mozilla-central/file/84bd8d9f4256/js/src/tests/lib/tests.py#l12
            # as well as other interesting flag combinations that have found / may find new bugs.
            ['--fuzzing-safe', '--ion-offthread-compile=off'],  # compareJIT uses this first flag set as the sole baseline when fuzzing
            ['--fuzzing-safe', '--ion-offthread-compile=off', '--no-baseline'],  # Not in jit_test.py though...
            ['--fuzzing-safe', '--ion-offthread-compile=off', '--no-baseline', '--no-ion'],
            ['--fuzzing-safe', '--ion-offthread-compile=off', '--no-baseline', '--ion-eager'],  # Not in jit_test.py though...
            ['--fuzzing-safe', '--ion-offthread-compile=off', '--ion-eager'],  # Not in jit_test.py though...
            ['--fuzzing-safe', '--ion-offthread-compile=off', '--no-ion'], # Not in jit_test.py though, see bug 848906 comment 1
            ['--fuzzing-safe', '--ion-offthread-compile=off', '--no-fpu'],
        ]
        if shellSupportsFlag(shellPath, "--latin1-strings"):  # See bug 1028867
            basicFlagList.append(['--fuzzing-safe', '--baseline-eager', '--latin1-strings'])
        if shellSupportsFlag(shellPath, "--thread-count=1"):
            basicFlagList.append(['--fuzzing-safe', '--ion-offthread-compile=off', '--ion-eager'])
            # Range analysis had only started to stabilize around the time when --no-sse3 landed.
            if shellSupportsFlag(shellPath, '--no-sse3'):
                basicFlagList.append(['--fuzzing-safe', '--ion-offthread-compile=off',
                                      '--ion-eager', '--ion-check-range-analysis', '--no-sse3'])
        return basicFlagList
    elif shellSupportsFlag(shellPath, "--fuzzing-safe"):
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
            ['--fuzzing-safe', '--ion-parallel-compile=off', '--baseline-eager', '--no-ion'], # See bug 848906 comment 1
            ['--fuzzing-safe', '--ion-parallel-compile=off', '--baseline-eager', '--no-fpu'],
        ]
        if shellSupportsFlag(shellPath, "--thread-count=1"):
            basicFlagList.append(['--fuzzing-safe', '--ion-eager', '--ion-parallel-compile=off'])
            # Range analysis had only started to stabilize around the time when --no-sse3 landed.
            if shellSupportsFlag(shellPath, '--no-sse3'):
                basicFlagList.append(['--fuzzing-safe', '--ion-parallel-compile=off',
                                      '--ion-eager', '--ion-check-range-analysis', '--no-sse3'])
        return basicFlagList
    elif shellSupportsFlag(shellPath, "--baseline-eager"):
        basicFlagList = [
            # From http://hg.mozilla.org/mozilla-central/annotate/4236b1163508/js/src/jit-test/jit_test.py#l140
            [], # Here, compareJIT uses no flags as the sole baseline when fuzzing
            ['--no-baseline'],  # Not in jit_test.py as of rev c6bca8768874 though...
            ['--no-baseline', '--no-ion', '--no-ti'],
            ['--no-baseline', '--no-ion'],
            ['--no-baseline', '--ion-eager'],  # Not in jit_test.py as of rev c6bca8768874 though...
            ['--ion-eager'],
            ['--baseline-eager'],
            ['--baseline-eager', '--no-ion'], # See bug 848906 comment 1
            ['--baseline-eager', '--no-ti'],  # Not in jit_test.py as of rev c6bca8768874 though...
            ['--baseline-eager', '--no-ti', '--no-fpu'],
        ]
        return basicFlagList
    elif shellSupportsFlag(shellPath, "--no-ion"):
        basicFlagList = [
            # From https://bugzilla.mozilla.org/attachment.cgi?id=616725
            [], # Here, compareJIT uses no flags as the sole baseline when fuzzing
            ['--no-jm'],
            ['--ion-gvn=off', '--ion-licm=off'],
            ['--no-ion', '--no-jm', '--no-ti'],
            ['--no-ion', '--no-ti'],
            ['--no-ion', '--no-ti', '-a', '-d'],
            ['--no-ion', '--no-jm'],
            ['--no-ion'],
            ['--no-ion', '-a'],
            ['--no-ion', '-a', '-d'],
            ['--no-ion', '-d'],
            # Plus a special bonus
            ['--ion-eager'],
        ]
        if shellSupportsFlag(shellPath, "--no-baseline"):
            basicFlagList.extend([
                ['--no-baseline'],
                ['--no-baseline', '--no-ti'],
            ])
        return basicFlagList
    else:
        sets = [
            # ,m,am,amd,n,mn,amn,amdn,mdn
            [],
            ['-m'],
            ['-m', '-a'],
            ['-m', '-a', '-d']
        ]
        if shellSupportsFlag(shellPath, '-n'):
            sets.extend([
                ['-n'],
                ['-m', '-n'],
                ['-m', '-n', '-a'],
                ['-m', '-n', '-a', '-d'],
                ['-m', '-n', '-d']
            ])
        if shellSupportsFlag(shellPath, "--ion"):
            sets += [["--ion"] + set for set in sets]
        return sets


# Consider adding a function (for compareJIT reduction) that takes a flag set
# and returns all its (meaningful) subsets.


def testRandomFlags():
    import sys
    for i in range(100):
        print ' '.join(randomFlagSet(sys.argv[1]))


if __name__ == "__main__":
    testRandomFlags()

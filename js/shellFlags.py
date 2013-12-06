import random
import os
import sys
from multiprocessing import cpu_count

from inspectShell import shellSupports

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
from subprocesses import isARMv7l, isWin64

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

    ion = shellSupportsFlag(shellPath, "--ion") and chance(.7)
    infer = chance(.7)

    if shellSupportsFlag(shellPath, '--fuzzing-safe'):
        args.append("--fuzzing-safe")  # --fuzzing-safe landed in bug 885361

    if (shellSupportsFlag(shellPath, '--no-sse3') and shellSupportsFlag(shellPath, '--no-sse4')) \
            and chance(.2):
        # --no-sse3 and --no-sse4 landed in m-c rev 526ba3ace37a.
        if chance(.5):
            args.append("--no-sse3")
        else:
            args.append("--no-sse4")

    if shellSupportsFlag(shellPath, '--no-fpu') and chance(.2):
        args.append("--no-fpu")  # --no-fpu landed in bug 858022

    # Remove the following isWin64 block when bug 944278 is fixed.
    if isWin64 or (shellSupportsFlag(shellPath, '--no-asmjs') and chance(.5)):
        args.append("--no-asmjs")

    # --baseline-eager landed after --no-baseline on the IonMonkey branch prior to landing on m-c.
    if shellSupportsFlag(shellPath, '--baseline-eager'):
        if chance(.3):
            args.append('--no-baseline')
        # elif is important, as we want to call --baseline-eager only if --no-baseline is not set.
        elif chance(.6):
            args.append("--baseline-eager")

    if cpu_count() > 1 and shellSupportsFlag(shellPath, '--ion-parallel-compile=on'):
        # Turns on parallel compilation for threadsafe builds.
        if chance(.7):
            args.append("--ion-parallel-compile=on")
            totalThreads = random.randint(2, (cpu_count() * 2))
            args.append('--thread-count=' + str(totalThreads))

    if not infer:
        args.append("--no-ti")

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
            if chance(.5):
                args.append('--ion-regalloc=lsra')  # On by default
            # Backtracking and stupid landed in m-c changeset dc4887f61d2e
            elif shellSupportsFlag(shellPath, '--ion-regalloc=backtracking') and chance(.4):
                args.append('--ion-regalloc=backtracking')
            # Disabled until bug 871848 is fixed.
            #elif shellSupportsFlag(shellPath, '--ion-regalloc=stupid') and chance(.2):
            #    args.append('--ion-regalloc=stupid')
        if shellSupportsFlag(shellPath, '--ion-compile-try-catch'):
            if chance(.5):
                args.append('--ion-compile-try-catch')
        # Disabled --ion-check-range-analysis for bug 944321
        #if shellSupportsFlag(shellPath, '--ion-check-range-analysis'):
        #    if chance(.5):
        #        args.append('--ion-check-range-analysis')
    else:
        args.append("--no-ion")

    # This is here because of bug 830508
    if shellSupportsFlag(shellPath, "--execute=enableSPSProfilingAssertions(true)") and chance(.5):
        if chance(.5):
            args.append("--execute=enableSPSProfilingAssertions(true)")
        else:
            args.append("--execute=enableSPSProfilingAssertions(false)")

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
    if shellSupportsFlag(shellPath, "--fuzzing-safe"):
        basicFlagList = [
            # Parts of this flag permutation come from:
            # http://hg.mozilla.org/mozilla-central/annotate/c6bca8768874/js/src/jit-test/jit_test.py#l140
            # as well as other interesting flag combinations that have found / may find new bugs.
            ['--fuzzing-safe'],  # compareJIT uses this first flag set as the sole baseline when fuzzing
            ['--fuzzing-safe', '--no-baseline'],  # Not in jit_test.py though...
            ['--fuzzing-safe', '--no-baseline', '--no-ion', '--no-ti'],
            ['--fuzzing-safe', '--no-baseline', '--no-ion'],
            ['--fuzzing-safe', '--no-baseline', '--ion-eager'],  # Not in jit_test.py though...
            ['--fuzzing-safe', '--ion-eager'],
            ['--fuzzing-safe', '--baseline-eager'],
            ['--fuzzing-safe', '--baseline-eager', '--no-ion'], # See bug 848906 comment 1
            ['--fuzzing-safe', '--baseline-eager', '--no-ti'],  # Not in jit_test.py though...
            ['--fuzzing-safe', '--baseline-eager', '--no-ti', '--no-fpu'],
        ]
        # Range analysis had only started to stabilize around the time when --no-sse3 landed.
        # Disabled --ion-check-range-analysis for bug 944321
        #if shellSupportsFlag(shellPath, '--no-sse3'):
        #    basicFlagList.append(['--fuzzing-safe',
        #                          '--ion-eager', '--ion-check-range-analysis', '--no-sse3'])
        # Remove the following isWin64 block when bug 944278 is fixed.
        if isWin64:
            basicFlagList.append(['--fuzzing-safe', '--no-asmjs'])
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

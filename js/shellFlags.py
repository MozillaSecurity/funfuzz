from __future__ import with_statement

import random
import os
import subprocess
import sys

from inspectShell import shellSupports

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
from countCpus import cpuCount

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

    jaeger = chance(.7)
    ion = shellSupportsFlag(shellPath, "--ion") and chance(.7)
    infer = chance(.7)

    # --baseline-eager landed after --no-baseline on the IonMonkey branch prior to landing on m-c.
    if shellSupportsFlag(shellPath, '--baseline-eager'):
        if chance(.3):
            args.append('--no-baseline')
        # elif is important, as we want to call --baseline-eager only if --no-baseline is not set.
        elif chance(.6):
            args.append("--baseline-eager")

    if cpuCount() > 1 and shellSupportsFlag(shellPath, '--ion-parallel-compile=on'):
        # Turns on parallel compilation for threadsafe builds.
        if chance(.7):
            args.append("--ion-parallel-compile=on")
            totalThreads = random.randint(2, (cpuCount() * 2))
            args.append('--thread-count=' + str(totalThreads))

    if shellSupportsFlag(shellPath, "--no-ion"):
        # New js shell defaults jaeger, ion, and infer to on! See bug 724751.
        if not jaeger:
            args.append("--no-jm")
        if not ion:
            args.append("--no-ion")
        if not infer:
            args.append("--no-ti")
    else:
        # Old shells (and xpcshell?) default jaeger, ion, and infer to off.
        if jaeger:
            args.append("-m")
        if ion:
            args.append("--ion")
        if infer:
            args.append("-n")

    if jaeger:
        if chance(.5):
            args.append("-a") # aka --always-mjit
        if chance(.2):
            args.append("-d") # aka --debugjit
        if chance(.2):
            args.append("--execute=mjitChunkLimit(" + str(random.randint(5, 100)) + ")")

    if ion:
        if chance(.6):
            args.append("--ion-eager")
        if chance(.2):
            args.append("--ion-gvn=" + random.choice(["off", "pessimistic", "optimistic"]))
        if chance(.2):
            args.append("--ion-licm=off")
        if chance(.2):
            args.append("--ion-range-analysis=off")
        if chance(.2):
            args.append("--ion-inlining=off")
        if chance(.2):
            args.append("--ion-osr=off")
        if chance(.2):
            args.append("--ion-limit-script-size=off")

    # This is here because of bug 830508
    # This will all be Falsed due to bug 865471, which breaks jsfunfuzz
    if False and shellSupportsFlag(shellPath, "--execute=enableSPSProfilingAssertions(true)") and chance(.5):
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
    if shellSupportsFlag(shellPath, "--baseline-eager"):
        basicFlagList = [
            # From http://hg.mozilla.org/projects/ionmonkey/annotate/280e5ed3f0b7/js/src/jit-test/jit_test.py#l140
            [], # Here, compareJIT uses no flags as the sole baseline when fuzzing
            ['--no-baseline'],
            ['--no-baseline', '--no-jm'],
            ['--no-baseline', '--no-ion', '--no-jm', '--no-ti'],
            ['--no-baseline', '--no-ion', '--no-ti'],
            ['--no-baseline', '--no-ion', '--no-ti', '-a', '-d'],
            ['--no-baseline', '--no-ion', '--no-jm'],
            ['--no-baseline', '--no-ion'],
            ['--no-baseline', '--no-ion', '-a'],
            ['--no-baseline', '--no-ion', '-a', '-d'],
            ['--no-baseline', '--no-ion', '-d'],
            ['--no-baseline', '--ion-eager'],
            ['--ion-eager'],
            ['--baseline-eager'],
            ['--baseline-eager', '--no-ion'], # See bug 848906 comment 1
            ['--baseline-eager', '--no-ti'],
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
                # ['--baseline-eager'],
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

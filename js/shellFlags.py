from __future__ import with_statement

import random
import os
import subprocess

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
        if chance(.4):
            args.append("-a") # aka --always-mjit
        if chance(.2):
            args.append("-d") # aka --debugjit
        if chance(.2):
            args.append("--execute=mjitChunkLimit(" + str(random.randint(5, 100)) + ")")

    if ion:
        if chance(.4):
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

    #if chance(.05):
    #    args.append("--execute=verifyprebarriers()")
    #if chance(.05):
    #    args.append("--execute=verifypostbarriers()")

    if chance(.05):
        args.append("-D") # aka --dump-bytecode

    if chance(.2):
        # jorendorff suggests the following line for E4X. It should be removed when E4X is removed.
        args.extend(['-e', '\'options("allow_xml");\''])

    return args


def basicFlagSets(shellPath):
    if shellSupportsFlag(shellPath, "--no-ion"):
        # From https://bugzilla.mozilla.org/attachment.cgi?id=616725
        return [
            [],
            ['--no-jm'],
            ['--ion-gvn=off', '--ion-licm=off'],
            ['--no-ion', '--no-jm', '--no-ti'],
            ['--no-ion', '--no-ti'],
            ['--no-ion', '--no-ti', '-a', '-d'],
            ['--no-ion', '--no-jm'],
            ['--no-ion'],
            ['--no-ion', '-a'],
            ['--no-ion', '-a', '-d'],
            ['--no-ion', '-d']
        ]
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


def shellSupports(shellPath, args):
    '''
    This function returns True if the shell likes the args.
    You can support for a function, e.g. ['-e', 'foo()'], or a flag, e.g. ['-j', '-e', '42'].
    '''
    cmdList = [shellPath] + args

    vdump(' '.join(cmdList))
    cfgEnvDt = deepcopy(os.environ)
    if isLinux:
        cfgEnvDt['LD_LIBRARY_PATH'] = os.path.dirname(os.path.abspath(shellPath))
    out, retCode = captureStdout(cmdList, ignoreStderr=True, combineStderr=True,
                                 ignoreExitCode=True, env=cfgEnvDt)
    vdump('The return code is: ' + str(retCode))

    if retCode == 0:
        return True
    elif 1 <= retCode <= 3:
        # Exit codes 1 through 3 are all plausible "non-support":
        #   * "Usage error" is 1 in new js shell, 2 in old js shell, 2 in xpcshell.
        #   * "Script threw an error" is 3 in most shells, but 1 in some versions (see bug 751425).
        # Since we want autoBisect to support all shell versions, allow all these exit codes.
        return False
    else:
        raise Exception('Unexpected exit code in shellSupports ' + str(retCode))

def testRandomFlags():
    import sys
    for i in range(100):
        print ' '.join(randomFlagSet(sys.argv[1]))


if __name__ == "__main__":
    testRandomFlags()

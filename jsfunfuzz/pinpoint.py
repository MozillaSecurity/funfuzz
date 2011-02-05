#!/usr/bin/env python

import os
import subprocess

from fnStartjsfunfuzz import archOfBinary, testDbgOrOpt, testJsShellOrXpcshell

p0=os.path.dirname(__file__)
lithiumpy = os.path.abspath(os.path.join(p0, "..", "lithium", "lithium.py"))
autobisectpy = os.path.abspath(os.path.join(p0, "..", "js-autobisect", "autoBisect.py"))

def pinpoint(itest, logPrefix, jsEngine, engineFlags, infilename, bisectRepo, alsoRunChar=True):
    """
       Run Lithium and autobisect.

       itest must be an array of the form [module, ...] where module is an interestingness module.
       The module's "interesting" function must accept [...] + [jsEngine] + engineFlags + infilename
       (If it's not prepared to accept engineFlags, engineFlags must be empty.)
    """

    if testJsShellOrXpcshell(jsEngine) == 'xpcshell':
        raise Exception('Lithium and autoBisect cannot yet work [together] on xpcshell.')

    lith1tmp = logPrefix + "-lith1-tmp"
    os.mkdir(lith1tmp)
    lithArgs = itest + [jsEngine] + engineFlags + [infilename]
    print ' '.join([lithiumpy] + lithArgs)
    subprocess.call(["python", lithiumpy, "--tempdir=" + lith1tmp] + lithArgs, stdout=open(logPrefix + "-lith1-out", "w"))

    if alsoRunChar:
        lith2tmp = logPrefix + "-lith2-tmp"
        os.mkdir(lith2tmp)
        lith2Args = ["--char"] + lithArgs
        print ' '.join([lithiumpy] + lith2Args)
        subprocess.call(["python", lithiumpy, "--tempdir=" + lith2tmp] + lith2Args, stdout=open(logPrefix + "-lith2-out", "w"))

    print "Done running Lithium. To reproduce, run:"
    print ' '.join([lithiumpy, "--strategy=check-only"] + lithArgs)

    jsEngineName = os.path.basename(jsEngine)
    if bisectRepo is not "none":
        autobisectCmd = ["python", autobisectpy, "-d", bisectRepo, "-i", "-p", "-a", archOfBinary(jsEngine), "-c", testDbgOrOpt(jsEngine)] + engineFlags + [infilename] + itest
        print ' '.join(autobisectCmd)
        subprocess.call(autobisectCmd, stdout=open(logPrefix + "-autobisect", "w"), stderr=subprocess.STDOUT)
        print "Done running autobisect"

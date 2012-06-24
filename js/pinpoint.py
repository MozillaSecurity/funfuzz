#!/usr/bin/env python

import os
import shutil
import subprocess
import sys
#import tarfile

from inspectShell import archOfBinary, testDbgOrOpt, testJsShellOrXpcshell

p0 = os.path.dirname(os.path.abspath(__file__))
lithiumpy = os.path.abspath(os.path.join(p0, os.pardir, 'lithium', 'lithium.py'))
autobisectpy = os.path.abspath(os.path.join(p0, os.pardir, 'autoBisectJs', 'autoBisect.py'))
shellBeautificationpy = os.path.join(p0, 'shellBeautification.py')

path2 = os.path.abspath(os.path.join(p0, os.pardir, 'util'))
sys.path.append(path2)
from subprocesses import captureStdout, shellify
import lithOps

def tempdir(path):
    os.mkdir(path)
    return "--tempdir=" + path

def pinpoint(itest, logPrefix, jsEngine, engineFlags, infilename, bisectRepo, targetTime, alsoRunChar=True, alsoReduceEntireFile=False):
    """
       Run Lithium and autobisect.

       itest must be an array of the form [module, ...] where module is an interestingness module.
       The module's "interesting" function must accept [...] + [jsEngine] + engineFlags + infilename
       (If it's not prepared to accept engineFlags, engineFlags must be empty.)
    """

    valgrindSupport = "--valgrind" in itest
    valgrindX = ["--valgrind"] if valgrindSupport else []

    lithArgs = itest + [jsEngine] + engineFlags + [infilename]
    (lithResult, lithDetails) = lithOps.runLithium(lithArgs, logPrefix + "-1-lines", targetTime)

    if lithResult == lithOps.LITH_FINISHED and targetTime is None:
        lith2Args = ["--char"] + lithArgs
        print shellify([lithiumpy] + lith2Args)
        (lithResult, lithDetails) = lithOps.runLithium(lith2Args, logPrefix + "-2-chars", targetTime)

    print
    print "Done running Lithium on the part in between DDBEGIN and DDEND. To reproduce, run:"
    print shellify([lithiumpy, "--strategy=check-only"] + lithArgs)
    print

    # Check that the testcase is interesting.
    if False and alsoReduceEntireFile and lithResult == lithOps.LITH_FINISHED:
        # FIXME: continue replacing direct calls to Lithium with calls to lithOps.runLithium, then remove the tempDir function.

        # Beautify the output. This will remove DDBEGIN and DDEND as they are comments.
        # This will output a file with the '-beautified' suffix.
        # Reduce once using toString decompile method.
        subprocess.call([sys.executable, shellBeautificationpy, '--shell=' + jsEngine, "--decompilationType=uneval", infilename])

        print 'Operating on the beautified testcase for the n-th time where n =',
        # iterNum starts from 3 because lith1 and lith2 are already used above.
        iterNumStart = 3 if alsoRunChar is True else 2
        iterNum = iterNumStart
        # Run Lithium on the testcase 10 more times, but run it using char only for 3 tries of toString and uneval reduction each.
        # Generally, lines don't get significantly reduced after the 3rd try of line reduction.
        MAX_BEAUTIFIED_LITHIUM_RUNS = iterNumStart + 10
        while(iterNum < MAX_BEAUTIFIED_LITHIUM_RUNS):
            print iterNum - 2,
            # Operate on the beautified version first.
            lithArgs = lithArgs[0:-1]
            beautifiedFilename = infilename + '-beautified'
            lithArgs = lithArgs + [beautifiedFilename]
            # We must still be operating on the beautified version.
            assert beautifiedFilename in lithArgs
            # Check that the testcase is still interesting.
            beautifiedOutput = captureStdout([sys.executable, lithiumpy, "--strategy=check-only", tempdir(logPrefix + "-lith" + str(iterNum) + "-b-tmp")] + lithArgs)[0]
            if 'not interesting' not in beautifiedOutput:
                assert 'interesting' in beautifiedOutput
                # Overwrite the original -reduced file with the beautified version since it is interesting.
                shutil.move(beautifiedFilename, infilename)
                # Operate on the original -reduced file.
                lithArgs = lithArgs[0:-1]
                lithArgs = lithArgs + [infilename]
                assert beautifiedFilename not in lithArgs
                #print shellify([lithiumpy] + lithArgs)
                subprocess.call([sys.executable, lithiumpy, tempdir(logPrefix + '-lith' + str(iterNum) + '-tmp')] + lithArgs, stdout=open(logPrefix + "-lith" + str(iterNum) + "-out", "w"))

                # Run it using char only after 3 tries of toString and uneval reduction each.
                if alsoRunChar and (iterNum - 2) > ((MAX_BEAUTIFIED_LITHIUM_RUNS - iterNumStart) // 2):
                    iterNum += 1
                    print iterNum - 2,
                    print '(operating on chars..)',
                    assert iterNum in (9, 11, 13)  # Refer to reduction method below
                    lith2Args = ["--char"] + lithArgs
                    assert beautifiedFilename not in lith2Args
                    #print shellify([lithiumpy] + lith2Args)
                    subprocess.call([sys.executable, lithiumpy, tempdir(logPrefix + '-lith' + str(iterNum) + '-tmp')] + lith2Args, stdout=open(logPrefix + "-lith" + str(iterNum) + "-out", "w"))
            else:
                # Beautified testcase is no longer interesting.
                print 'Beautified testcase is no longer interesting!'
                break
            iterNum += 1
            # We want the following reduction method:
            # iterNum 3: uneval
            # iterNum 4: toString
            # iterNum 5: uneval
            # iterNum 6: toString
            # iterNum 7: uneval
            # iterNum 8: toString
            # iterNum 9: char
            # iterNum 10: uneval
            # iterNum 11: char
            # iterNum 12: toString
            # iterNum 13: char
            if iterNum < MAX_BEAUTIFIED_LITHIUM_RUNS:
                # This will output a file with the '-beautified' suffix.
                # Rotate between reducing using the toString and uneval decompile method
                if alsoRunChar:
                    if iterNum % 2 == 0 and iterNum != 10:
                        # toString
                        assert iterNum in (4, 6, 8, 12)
                        subprocess.call([sys.executable, shellBeautificationpy, '--shell=' + jsEngine, "--decompilationType=toString", infilename])
                    else:
                        # uneval
                        # iterNum 3 has already occurred prior to the increment of iterNum above.
                        assert iterNum in (5, 7, 10)
                        subprocess.call([sys.executable, shellBeautificationpy, '--shell=' + jsEngine, "--decompilationType=uneval", infilename])
                else:
                    # If alsoRunChar is false, which occurs when jsInteresting.py is operating at JS_DID_NOT_FINISH and below. iterNumStart also starts from 2.
                    if iterNum % 2 != 0:
                        # toString
                        assert iterNum in (3, 5, 7, 9, 11, 13)
                        subprocess.call([sys.executable, shellBeautificationpy, '--shell=' + jsEngine, "--decompilationType=toString", infilename])
                    else:
                        # uneval
                        # iterNum 3 has already occurred prior to the increment of iterNum above.
                        assert iterNum in (4, 6, 8, 10, 12)
                        subprocess.call([sys.executable, shellBeautificationpy, '--shell=' + jsEngine, "--decompilationType=uneval", infilename])
            else:
                print

        # Operate on the original -reduced file.
        lithArgs = lithArgs[0:-1]
        lithArgs = lithArgs + [infilename]
        assert beautifiedFilename not in lithArgs
        # Check that the testcase is still interesting after the extra beautified lithium reductions.
        finalBeautifiedOutput = captureStdout([sys.executable, lithiumpy, "--strategy=check-only", tempdir(logPrefix + "-lith-final-tmp")] + lithArgs)[0]
        if 'not interesting' not in finalBeautifiedOutput:
            assert 'interesting' in finalBeautifiedOutput

        # Archive all wXX-lith*-tmp directories in a tarball.
        #lithTmpDirTarball = tarfile.open('tempName.tar.bz2', 'w:bz2')
        #for loop from 1 to iterNum
            #lithTmpDirTarball.add(logPrefix + '-lith' + str(iterNum) + '-tmp')
        #lithTmpDirTarball.close()

    if bisectRepo is not "none" and targetTime is None:
        # We cannot test that it is not xpcshell with Python 2.5 since testJsShellOrXpcshell relies
        # on 'delete' being a keyword argument in NamedTemporaryFile(). The testing functions in
        # inspectShell in general need at least Python 2.6 because of this.
        if sys.version_info >= (2, 6) and testJsShellOrXpcshell(jsEngine) != "xpcshell":
            autobisectCmd = [sys.executable, autobisectpy] + valgrindX + ["-d", bisectRepo, "-i", "-p", "-a", archOfBinary(jsEngine), "-c", testDbgOrOpt(jsEngine), ("--flags=" + ','.join(engineFlags)) if engineFlags else ""] + [infilename] + itest
            print shellify(autobisectCmd)
            subprocess.call(autobisectCmd, stdout=open(logPrefix + "-autobisect", "w"), stderr=subprocess.STDOUT)
            print "Done running autobisect. Log: " + logPrefix + "-autobisect"
        elif sys.version_info < (2, 6):
            print 'Not pinpointing to exact changeset, please use a Python version >= 2.6.'

    return (lithResult, lithDetails)

#!/usr/bin/env python
#
#/* ***** BEGIN LICENSE BLOCK	****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is startjsfunfuzz.
#
# The Initial Developer of the Original Code is
# Gary Kwong.
# Portions created by the Initial Developer are Copyright (C) 2008-2010
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.

# This file contains functions for startjsfunfuzz.py.

import os, shutil, subprocess, platform

verbose = True  # Turn this to True to enable verbose output for debugging.


# These functions throw various custom exceptions.
def exceptionBadCompileType():
    raise Exception('Unknown compileType')
def exceptionBadBranchType():
    raise Exception('Unknown branchType')
def exceptionBadOs():
    raise Exception("Unknown OS - Platform is unsupported.")


# This function checks for supported operating systems.
# It returns macVer in the case of 10.6.x.
def osCheck():
    if os.name == 'posix':
        if os.uname()[0] == 'Darwin':
            macVer, _, _ = platform.mac_ver()
            macVer = float('.'.join(macVer.split('.')[:2]))
            if ('10.6' in str(macVer)):
                return macVer
            else:
                exceptionBadOs()  # Only 10.6.x is supported.
        elif os.uname()[0] == 'Linux':
            pass
    elif os.name == 'nt':
        pass
    else:
        print '\nOnly Windows XP/Vista/7, Linux or Mac OS X 10.6.x are supported.\n'
        raise Exception('Unknown OS - Platform is unsupported.')

# This function prints the corresponding CLI requirements that should be input.
def error(branchSupp):
    print '\n==========\n| Error! |\n=========='
    print 'General usage: python startjsfunfuzz.py [32|64] [dbg|opt]',
    print '%s [patch <directory to patch>] [patch <directory to patch>]' % branchSupp,
    print '[valgrind]\n'
    print
    print 'System requirements: Python 2.6.x, Mozilla build prerequisites and repositories at "~/" (POSIX) or "/" (NT).'
    print
    print 'Windows platforms only compile in 32-bit.'
    print 'Linux platforms only compile in 64-bit.'
    print 'Valgrind only works for Linux platforms.'
    print 'Choice of a 32-bit or 64-bit binary is only applicable to Mac OS X 10.6.x.\n'

# This function captures standard output into a python string.
def captureStdout(input):
    p = subprocess.Popen([input], stdin=subprocess.PIPE,stdout=subprocess.PIPE, shell=True)
    (stdout, stderr) = p.communicate()
    return stdout

# This function finds the mercurial revision and appends it to the directory name.
# It also prompts if the user wants to continue, should the repository not be on tip.
def hgHashAddToFuzzPath(fuzzPath):
    if verbose:
        print '\nDEBUG - About to start running `hg identify` commands...'
    tipOrNot = captureStdout('hg identify')[:-1]
    hgIdentifynMinus1 = captureStdout('hg identify -n')[:-1]
    # -5 is to remove the " tip\n" portion of `hg identify` output if on tip.
    hgIdentifyMinus5 = captureStdout('hg identify')[:-5]
    onTip = True
    if tipOrNot.endswith('tip'):
        fuzzPath2 = fuzzPath[:-1] + '-' + hgIdentifynMinus1
        fuzzPath = fuzzPath2 + '-' + hgIdentifyMinus5
    else:
        print '`hg identify` shows the repository is on this changeset -', hgIdentifynMinus1 + ':' + tipOrNot
        notOnTipApproval = str(raw_input('Not on tip! Are you sure you want to continue? (y/n): '))
        if notOnTipApproval == ('y' or 'yes'):
            onTip = False
            fuzzPath = fuzzPath[:-1] + '-' + hgIdentifynMinus1 + '-' + tipOrNot
        else:
            switchToTipApproval = str(raw_input('Do you want to switch to the default tip? (y/n): '))
            if switchToTipApproval == ('y' or 'yes'):
                subprocess.call(['hg up default'], shell=True)
                fuzzPath2 = fuzzPath[:-1] + '-' + hgIdentifynMinus1
                fuzzPath = fuzzPath2 + '-' + hgIdentifyMinus5
            else:
                raise Exception('Not on tip.')
    fuzzPath += '/'
    if verbose:
        print '\nDEBUG - Finished running `hg identify` commands.'
    return fuzzPath, onTip

# This function copies the js tree or the pymake build directory.
def cpJsTreeOrPymakeDir(repo, jsOrBuild):
    repo += 'js/src/' if jsOrBuild == 'js' else 'build/'
    if os.name == 'posix':
        repo = os.path.expanduser(repo)
    try:
        jsOrBuildText = 'js tree' if jsOrBuild == 'js' else 'pymake build dir'
        if verbose:
            print 'DEBUG - Copying the', jsOrBuildText, 'to the fuzzPath, which is located at', repo
        shutil.copytree(repo, "compilePath") if jsOrBuild == 'js' else shutil.copytree(repo, "build")
        if verbose:
            print 'DEBUG - Finished copying the', jsOrBuildText, 'to the fuzzPath.'
    except OSError:
        raise Exception("The', jsOrBuildText, 'directory located at '" + repo + "' doesn't exist!")

# This function compiles a js binary depending on the parameters.
def configureJsBinary(archNum, compileType, branchType, valgrindSupport, threadsafe):
    configureCmd = 'sh ../configure'
    if (archNum == '32') and (os.name == 'posix'):
        if os.uname()[0] == "Darwin":
            configureCmd = 'CC="gcc-4.2 -arch i386" CXX="g++-4.2 -arch i386" ' + \
                         'HOST_CC="gcc-4.2" HOST_CXX="g++-4.2" ' + \
                         'RANLIB=ranlib AR=ar AS=$CC LD=ld' + \
                         'STRIP="strip -x -S" CROSS_COMPILE=1' + \
                         'sh ../configure --target=i386-apple-darwin8.0.0'
    if compileType == 'dbg':
        configureCmd += ' --disable-optimize --enable-debug'
    elif compileType == 'opt':
        configureCmd += ' --enable-optimize --disable-debug'

    if branchType == 'jm':
        configureCmd += ' --enable-methodjit'
    if valgrindSupport:
        configureCmd += ' --enable-valgrind'
    if threadsafe:
        configureCmd += ' --enable-threadsafe --with-system-nspr'

    if verbose:
        print 'DEBUG - This is the configure command:'
        print 'DEBUG - %s\n' % configureCmd

    subprocess.call([configureCmd], shell=True)

# This function compiles and copies a binary.
def compileCopy(archNum, compileType, branchType, usePymake):
    # Run make using 2 cores, not sure if pymake allows parallel compilation yet.
    subprocess.call(['python', '-O', '../../build/pymake/make.py', '-j2']) if usePymake else subprocess.call(['make', '-j2'])
    # Sniff platform and rename executable accordingly:
    if os.name == 'posix':
        shellName = 'js-' + compileType + '-' + archNum + '-' + branchType + '-' + os.uname()[0].lower()
        shutil.copy2('js', '../../' + shellName)
    elif os.name == 'nt':
        shellName = 'js-' + compileType + '-' + archNum + '-' + branchType + '-' + os.name.lower()
        shutil.copy2('js.exe', '../../' + shellName + '.exe')
    return shellName

# This function tests if a binary is 32-bit or 64-bit.
def test32or64bit(jsShellName, archNum):
    test32or64bitCmd = 'file ' + jsShellName
    test32or64bitStr = captureStdout(test32or64bitCmd)[:-1]
    if archNum == '32':
        if verbose:
            # Searching the last 10 characters will be sufficient.
            if 'i386' in test32or64bitStr[-10:]:
                print 'test32or64bitStr is:', test32or64bitStr
                print 'DEBUG - Compiled binary is 32-bit.'
        if 'i386' not in test32or64bitStr[-10:]:
            raise Exception('Compiled binary is not 32-bit.')
    elif archNum == '64':
        if verbose:
            if 'x86_64' in test32or64bitStr[-10:]:
                print 'test32or64bitStr is:', test32or64bitStr
                print 'DEBUG - Compiled binary is 64-bit.'
        if 'x86_64' not in test32or64bitStr[-10:]:
            raise Exception('Compiled binary is not 64-bit.')

# This function tests if a binary is a debug or optimized shell.
def testDbgOrOpt(jsShellName, compileType):
    # Create a testfile with the gczeal() function.
    subprocess.call(['echo \'gczeal()\' > compileTypeTest'], shell=True)
    if os.name == 'posix':
        testFileErrNum = subprocess.call(['./' + jsShellName, 'compileTypeTest'])
    elif os.name == 'nt':
        testFileErrNum = subprocess.call([jsShellName, 'compileTypeTest'], shell=True)
    os.remove('compileTypeTest')  # Remove testfile after grabbing the error code.

    if verbose:
        print 'DEBUG - The error code for debug shells should be 0.'
        print 'DEBUG - The error code for opt shells should be 3.'
        print 'DEBUG - The actual error code for', jsShellName, 'now, is:', str(testFileErrNum)

    # The error code for debug shells when passing in the gczeal() function should be 0.
    if compileType == 'dbg' and testFileErrNum != 0:
        print 'ERROR: A debug shell when tested with the gczeal() should return "0" as the error code.'
        print 'compileType is: ' + compileType
        print 'testFileErrNum is: ' + str(testFileErrNum)
        print
        raise Exception('The compiled binary is not a debug shell.')
    # The error code for debug shells when passing in the gczeal() function
    # should be 3, because they don't have the function compiled in.
    elif compileType == 'opt' and testFileErrNum != 3:
        print 'ERROR: An optimized shell when tested with the gczeal() should return "3" as the error code.'
        print 'compileType is: ' + compileType
        print 'testFileErrNum is: ' + str(testFileErrNum)
        print
        raise Exception('The compiled binary is not an optimized shell.')

if '__name__' == '__main__':
    pass

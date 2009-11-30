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
# Portions created by the Initial Developer are Copyright (C) 2006-2008
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

import os, shutil, subprocess

verbose = True  # Turn this to True to enable verbose output for debugging.

# This function prints verbose letterheads.
def verboseMsg():
    print "\nDEBUG - Debug output follows..."


# These functions throw various custom exceptions.
def exceptionBadOs():
    raise Exception("Unknown OS - Platform is unsupported.")

def exceptionBadCompileType():
    raise Exception("Unknown compileType - choose from [dbg|opt].")

def exceptionBadPosixBranchType():
    raise Exception("Not a supported POSIX branchType")

def exceptionBadNtBranchType():
    raise Exception("Not a supported NT branchType")


# This function prints the corresponding CLI requirements that should be input.
def error(supportedBranches):
    print """

==========
| Error! |
==========
"""
    print 'General usage: python startjsfunfuzz.py [32|64] [dbg|opt] ' + \
      '%s [patch <directory to patch>] [patch <directory to patch>]' \
    % supportedBranches
    print "Note that the choice of 32-bit or 64-bit binaries is only " + \
          "applicable to Mac OS X 10.6.x."


# This function copies the entire js source directory on POSIX (Linux / Mac)
# platforms.
def posixCopyJsTree(repo):
    try:
        if verbose:
            verboseMsg()
            print 'DEBUG - Copying the entire js tree to the fuzzPath'
        shutil.copytree(os.path.expanduser(repo + "js/src/"),"compilePath")
    except OSError:
        error()
        raise Exception("The js code repository directory located at '" + \
                        os.path.expanduser(repo + "js/src/") + \
                        "' doesn't exist!")


# This function copies the entire js source directory on Windows platforms.
def ntCopyJsTree(repo):
    try:
        if verbose:
            verboseMsg()
            print 'DEBUG - Copying the entire js tree to the fuzzPath'
        shutil.copytree(repo + "js/src/","compilePath")
    except OSError:
        error()
        raise Exception("The js code repository directory located at '" + \
                        repo + "js/src/' doesn't exist!")


# This function compiles debug builds, and Mac OS X 10.6.x compiles 64-bit by
# default, so this also provides the option of compiling 32-bit in 10.6.x only.
def dbgCompile(macVer, archNum):
    if ('10.6' not in str(macVer)) or (archNum == "64"):
        subprocess.call(['sh', '../configure', '--disable-optimize',
                         '--enable-debug'])
    else:  # if archNum == "32":
        subprocess.call(['CC="gcc-4.2 -arch i386" CXX="g++-4.2 -arch i386" ' +\
                         'HOST_CC="gcc-4.2" HOST_CXX="g++-4.2" ' + \
                         'RANLIB=ranlib AR=ar AS=$CC LD=ld' + \
                         'STRIP="strip -x -S" CROSS_COMPILE=1' + \
                         'sh ../configure ' + \
                         '--target=i386-apple-darwin8.0.0 ' + \
                         '--disable-optimize --enable-debug'], shell=True)


# This function compiles opt builds, and Mac OS X 10.6.x compiles 64-bit by
# default, so this also provides the option of compiling 32-bit in 10.6.x only.
def optCompile(macVer, archNum):
    if ('10.6' not in str(macVer)) or (archNum == "64"):
        subprocess.call(['sh', '../configure', '--enable-optimize',
                         '--disable-debug'])
    else:  # if archNum == "32":
        subprocess.call(['CC="gcc-4.2 -arch i386" CXX="g++-4.2 -arch i386" ' +\
                         'HOST_CC="gcc-4.2" HOST_CXX="g++-4.2" ' + \
                         'RANLIB=ranlib AR=ar AS=$CC LD=ld' + \
                         'STRIP="strip -x -S" CROSS_COMPILE=1' + \
                         'sh ../configure ' + \
                         '--target=i386-apple-darwin8.0.0 ' + \
                         '--enable-optimize --disable-debug'], shell=True)


# This function compiles and copies a binary.
def compileCopy(branchType, dbgOpt, archNum):
    # Run make using 2 cores.
    subprocess.call(["make", "-j2"])

    # Sniff platform and rename executable accordingly:
    if os.name == "posix":
        shellName = "js-" + dbgOpt + "-" + archNum + "-" + branchType + "-" + \
                    os.uname()[0].lower()
        shutil.copy2("js","../../" + shellName)
    elif os.name == "nt":
        shellName = "js-" + dbgOpt + "-" + archNum + "-" + branchType + "-" + \
                    os.name.lower()
        shutil.copy2("js.exe","../../" + shellName + ".exe")
    else:
        exceptionBadOs()
    return shellName


# This function captures standard output into a python string.
def captureStdout(input):
    p = subprocess.Popen([input],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE, shell=True)
    (stdout, stderr) = p.communicate()
    return stdout


# This function tests if a binary is 32-bit or 64-bit.
def test32or64bit(jsShellName, macVer, archNum):
    test32or64bitCmd = "file " + jsShellName
    test32or64bitStr = captureStdout(test32or64bitCmd)[:-1]
    if '10.6' not in str(macVer):
        pass
    elif archNum == "64":
        if verbose:
            verboseMsg()
            # Searching the last 10 characters will be sufficient.
            if 'x86_64' in test32or64bitStr[-10:]:
                print "DEBUG - Compiled binary is 64-bit."
        if 'x86_64' not in test32or64bitStr[-10:]:
            raise Exception("Compiled binary is not 64-bit.")
    elif archNum == "32":
        if verbose:
            verboseMsg()
            if 'i386' in test32or64bitStr[-10:]:
                print "DEBUG - Compiled binary is 32-bit."
        if 'i386' not in test32or64bitStr[-10:]:
            raise Exception("Compiled binary is not 32-bit.")
    else:
        raise


# This function identifies the mercurial revision and appends it to the
# directory name. It also prompts if the user wants to continue should the
# repository not be on tip.
def hgHashAddToFuzzPath(fuzzPath):
    tipOrNot = captureStdout("hg identify")[:-1]
    if tipOrNot.endswith('tip'):
        fuzzPath = fuzzPath[:-1] + "-" + captureStdout("hg identify -n")[:-1]
        fuzzPath = fuzzPath + "-" + captureStdout("hg identify")[:-5]
    else:
        print '`hg identify` shows the repository is on this changeset -', \
            captureStdout("hg identify -n")[:-1] + ':' + tipOrNot
        notOnTipApproval = str(raw_input("Not on tip! Are you sure you want " +
                                         "to continue? (y/n): "))
        if notOnTipApproval == ("y" or "yes"):
            fuzzPath = fuzzPath + "-" + captureStdout("hg identify")[:-1]
        else:
            switchToTipApproval = str(raw_input("Do you want to switch to " +
                                                "the default tip? (y/n): "))
            if switchToTipApproval == ("y" or "yes"):
                subprocess.call(["hg up default"], shell=True)
                fuzzPath = fuzzPath[:-1] + "-" + \
                    captureStdout("hg identify -n")[:-1]
                fuzzPath = fuzzPath + "-" + captureStdout("hg identify")[:-5]
            else:
                raise Exception("Not on tip.")
    return fuzzPath


if '__name__' == '__main__':
    pass

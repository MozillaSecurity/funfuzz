#!/usr/bin/env python

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
# The Original Code is autoBisect.
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
#
# * ***** END LICENSE BLOCK	****	/

#import os, subprocess
from optparse import OptionParser



def optparseFunction():
    # bash ~/Desktop/autoBisect.sh ~/Desktop/2interesting/563210.js dbg bug "ssertion fail" # REPLACEME
    #usage = 'Usage: %prog -d <dir> -f "<js binary w/ optional parameters>"'
    usage = ''
    parser = OptionParser(usage)
    # See http://docs.python.org/library/optparse.html#optparse.OptionParser.disable_interspersed_args
    parser.disable_interspersed_args()
    parser.add_option('-d', '--dir', dest='dir', help='Source code directory')
    parser.add_option('-f', '--file', dest='file', help='File to be bisected')
    # -s --start startRepo
    # -e --end badRepo
    # -a --architecture 32 or 64
    # -b --bugOrWfm bug wfm bug by default
    # -o --output null by default
    # -j is on by default, action="store_true"
    # -m is off by default (methodJIT), default=False, action="store_true", dest=""??
    # Watch out for -w, --watchExitCode 3; this is for notExitCode, cat into interactive shell. Off by default
    (options, args) = parser.parse_args()
    return options.dir, options.file







#
#def main():
#    (dir, binaryAndParams) = optparseFunction()
#    (workingBugs, bugRetVal) = execBinaryParams(fileSearch(dir), binaryAndParams)
#
#    workingBugs.sort()
#    print '\nThe following bugs have js files that have weird return codes:'
#    for item in workingBugs:
#        print 'File number is:', item, 'and return value is:', bugRetVal[item]
#    print
#

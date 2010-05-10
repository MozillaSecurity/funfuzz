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
import sys
from optparse import OptionParser

def main():
    filename = sys.argv[-1:][0]
    (bugOrWfm, dir, output, startRepo, endRepo, archi, \
     tracingjitBool, methodjitBool, watchExitCode) = parseOpts()
    print (bugOrWfm, dir, output, startRepo, endRepo, archi, \
     tracingjitBool, methodjitBool, watchExitCode)
    print filename

# cat into interactive shell if passing as a CLI argument cannot reproduce the issue

# set the required compulsory flags - at least -s and -e

def parseOpts():

    usage = 'Usage: %prog [options] filename'
    parser = OptionParser(usage)
    # See http://docs.python.org/library/optparse.html#optparse.OptionParser.disable_interspersed_args
    parser.disable_interspersed_args()

    # autoBisect details
    parser.add_option('-b', '--bugOrWfm',
                      dest='bugOrWfm',
                      type='choice',
                      choices=['bug', 'wfm'],
                      default='bug',
                      help='(Optional, "bug" by default) ' + \
                           'Bisect to find a bug or WFM issue. ' + \
                           'Only accept values of "bug" or "wfm"')
    parser.add_option('-d', '--dir',
                      dest='dir',
                      help='Source code directory')
    parser.add_option('-o', '--output',
                      dest='output',
                      help='(Optional) Stdout or stderr output to be observed')

    # Define the start and end repositories.
    parser.add_option('-s', '--start',
                      dest='startRepo',
                      help='Start repository (earlier)')
    parser.add_option('-e', '--end',
                      dest='endRepo',
                      help='End repository (later)')

    # Define the architecture to be tested.
    parser.add_option('-a', '--architecture',
                      dest='archi',
                      type='choice',
                      choices=['32', '64'],
                      help='Test architecture. Only accept values of "32" or "64"')

    # Define parameters to be passed to the binary.
    parser.add_option('-j', '--tracingjit',
                      dest='tracingjitBool',
                      action='store_true',
                      default=False,
                      help='(Optional) Enable -j, tracing JIT when autoBisecting')
    parser.add_option('-m', '--methodjit',
                      dest='methodjitBool',
                      action='store_true',
                      default=False,
                      help='(Optional) Enable -m, method JIT when autoBisecting')

    # Special case in which a specific exit code needs to be observed.
    parser.add_option('-w', '--watchExitCode',
                      dest='watchExitCode',
                      type='choice',
                      choices=['3', '4', '5', '6'],
                      help='(Optional) Look out for a specific exit code in the range [3,6]')

    (options, args) = parser.parse_args()
    if len(args) != 1:
        parser.error("There is a wrong number of arguments.")
    return options.bugOrWfm, options.dir, options.output, \
            options.startRepo, options.endRepo, options.archi, options.tracingjitBool, \
            options.methodjitBool, options.watchExitCode

if __name__ == '__main__':
    main()

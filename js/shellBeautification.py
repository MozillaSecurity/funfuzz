#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import with_statement

import os
import shutil
import subprocess
import sys
from optparse import OptionParser

path0 = os.path.dirname(__file__)
path2 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path2)
from subprocesses import captureStdout

def main():

    # Parse options and parameters from the command-line.
    options = parseOpts()
    (filenameOld, jsShell, decompileType, overwriteOrigBool) = options

    # Output to a file which has "beautified" appended to the name.
    filename = filenameOld + '-beautified'
    shutil.copy2(filenameOld, filename)
    assert decompileType in ('toString', 'uneval')
    addAnonPrintFn(filename, decompileType)

    beautifiedOutputWithAnonPrintFn = captureStdout([jsShell, filename])[0]
    if decompileType == 'uneval':
        # Remove the '(function () {' and '})' at the bottom. Note the lack of \n.
        beautifiedOutputWithAnonPrintFn = beautifiedOutputWithAnonPrintFn[14:-2]
    assert beautifiedOutputWithAnonPrintFn != ''
    # The beautified output is highly unlikely that an empty function is returned
    # post-beautification. Thus, there is only a faint possibility that this assertion is hit.
    assert beautifiedOutputWithAnonPrintFn != '(function () {})'

    # Write the beautified contents with the anonymous print function back to the file.
    with open(filename, 'wb') as f:
        f.write(beautifiedOutputWithAnonPrintFn)

    lines = []
    linesExclEmptyLines = []
    # Read in the file contents as lines.
    with open(filename, 'rb') as f:
        lines = f.readlines()

    # Remove empty lines.
    for line in lines:
        # Remove whitespace, this should leave nothing behind if empty line was just "\n"
        if not line.strip():
            continue
        # Save the line since something else is present except whitespace
        else:
            if decompileType == 'toString':
                # Remove first 4 characters of whitespace when decompilationType toString is used.
                # Also put '{', '}' and ';' chars to a new line by themselves, except when the
                # " char and the 'return {' string is found, as well as regex matching.
                replaceLine = line[4:] if '    ' in line[:4] else line
                if '"' not in line and 'return' not in line and \
                   'match' not in line and 'for (' not in line:
                    linesExclEmptyLines.append(
                        replaceLine.replace('{', '\n{\n')
                                   .replace('}', '\n}\n')
                                   .replace(';', '\n;\n'))
                # We can try to put the entire for (...) condition on its own line.
                elif '"' not in line and 'return' not in line and \
                     'match' not in line and 'for (' in line:
                    linesExclEmptyLines.append(replaceLine.replace('{', '\n{\n'))
                else:
                    linesExclEmptyLines.append(replaceLine)
            elif decompileType == 'uneval':
                linesExclEmptyLines.append(line)

    # Write beautified file contents back to the file with empty lines removed.
    with open(filename, 'wb') as f:
        if decompileType == 'toString':
            # Remove the 'print(function(){\n' at the top and '})\n' at the bottom.
            f.writelines([line for line in linesExclEmptyLines[1:-1]])
        elif decompileType == 'uneval':
            f.writelines([line for line in linesExclEmptyLines])

    linesExclEmptyLinesTake2 = []
    # Read in the file contents as lines again.
    with open(filename, 'rb') as f:
        linesTake2 = f.readlines()

    # Remove empty lines again.
    for line2 in linesTake2:
        # Remove whitespace, this should leave nothing behind if empty line was just "\n"
        if not line2.strip():
            continue
        # Save the line since something else is present except whitespace
        else:
            linesExclEmptyLinesTake2.append(line2)

    # Write file contents back to the file with second round of empty lines removed.
    with open(filename, 'wb') as f:
        f.writelines([line for line in linesExclEmptyLinesTake2])

    # Overwrite the original file if the option is given.
    if overwriteOrigBool:
        shutil.move(filename, filenameOld)

def addAnonPrintFn(filename, typeOfDecompile):
    '''
    Wrap the entire file in an anonymous print function and have the js shell beautify it.
    '''
    fileHeader = ''
    fileFooter = ''
    if typeOfDecompile == 'toString':
        # FIXME: This will fail if there already is a (function(){ <some blob> } in the file.
        fileHeader = 'print(function(){\n'
        fileFooter = '\n})\n'
    elif typeOfDecompile == 'uneval':
        fileHeader = 'print(uneval(function(){\n'
        fileFooter = '\n}))\n'
    else:
        raise Exception('Not a known type of decompilation.')

    # Prepend the file.
    with open(filename, 'r+b') as file:
        oldContent = file.read()
        file.seek(0)
        file.write(fileHeader + oldContent)

    # Append with closing braces.
    with open(filename, 'ab') as file:
        file.write(fileFooter)

def parseOpts():
    usage = 'Usage: %prog [options] filename'
    parser = OptionParser(usage)
    # http://docs.python.org/library/optparse.html#optparse.OptionParser.disable_interspersed_args
    parser.disable_interspersed_args()

    parser.add_option('--shell',
                      dest='shell',
                      help='Specify js shell')
    parser.add_option('--decompilationType',
                      dest='decompilationType',
                      type='choice',
                      choices=['toString', 'uneval'],
                      default='toString',
                      help='Decompilation type. Defaults to "toString"')
    parser.add_option('--overwriteOrigFile',
                      dest='overwriteOrigBool',
                      action='store_true',
                      default=False,
                      help='Choose whether to overwrite the original file. Defaults to "False"')

    (options, args) = parser.parse_args()

    if len(args) < 1:
        parser.error('Not enough arguments')
    filename = args[0]

    if not options.shell:
        parser.error('Specify a js shell.')

    return filename, options.shell, options.decompilationType, options.overwriteOrigBool

try:
    main()
except AssertionError:
    print 'Beautification stage failed! Continuing... ',

#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os

def cpuCount():
    '''
    A version of cpu_count() that seems compatible with Python 2.5
    '''
    # POSIX platforms
    if hasattr(os, 'sysconf'):
        if os.sysconf_names.has_key('SC_NPROCESSORS_ONLN'):
            # Linux
            cpuNum = os.sysconf('SC_NPROCESSORS_ONLN')
            if cpuNum > 0 and isinstance(cpuNum, int):
                return cpuNum
        else:
            # Mac OS X
            return int(os.popen2('sysctl -n hw.ncpu')[1].read())
    # Windows
    if os.environ.has_key('NUMBER_OF_PROCESSORS'):
        cpuNum = int(os.environ['NUMBER_OF_PROCESSORS']);
        if cpuNum > 0:
            return cpuNum
    # Return 1 by default
    return 1

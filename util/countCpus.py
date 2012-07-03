import os

def cpuCount():
    '''
    A version of cpu_count() that seems compatible with Python 2.5
    Adapted from http://codeliberates.blogspot.com/2008/05/detecting-cpuscores-in-python.html
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

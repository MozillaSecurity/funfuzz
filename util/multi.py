#!/usr/bin/env python

import sys
import subprocess
import time
import platform

WIN = (platform.system() in ("Microsoft", "Windows"))
DEV_NULL = 'NUL' if WIN else '/dev/null'

if __name__ == "__main__":
    count = int(sys.argv[1])
    command = sys.argv[2:]
    close_fds = sys.platform != 'win32'
    for i in range(count):
        subprocess.Popen(command, close_fds=close_fds, stdout=open(DEV_NULL, 'w'), stderr=subprocess.STDOUT)
    # Leave this process running, in order to allow Ctrl+C to kill em all
    while True:
        time.sleep(10)

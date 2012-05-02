#!/usr/bin/env python

import platform
import subprocess
import sys
import time

if __name__ == "__main__":
    count = int(sys.argv[1])
    command = sys.argv[2:]
    close_fds = sys.platform != 'win32'
    for i in range(count):
        subprocess.Popen(command, close_fds=close_fds, stdout=open(os.devnull, 'w'), stderr=subprocess.STDOUT)
    # Leave this process running, in order to allow Ctrl+C to kill em all
    while True:
        time.sleep(10)

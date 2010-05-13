#!/usr/bin/env python

import sys
import subprocess
import time

if __name__ == "__main__":
  count = int(sys.argv[1])
  command = sys.argv[2:]
  for i in range(count):
    subprocess.Popen(command, close_fds=True, stdout=open('/dev/null', 'w'), stderr=subprocess.STDOUT)
  # Leave this process running, in order to allow Ctrl+C to kill em all
  while True:
    time.sleep(10)


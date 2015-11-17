#!/usr/bin/env python

# ulimit for memory does not work on OS X.
# So, I wrote this thing to kill off bloated processes before they:
#   * Cause slow thrashing
#   * Cause OS X to pause _other_ processes (and show the force quit window)
#   * Cause OS X to kernel panic
# I decided not to use 'psutil' or 'syrupy' and instead just parse |ps| output.

import os
import signal
import subprocess
import time


def reapOoms():
    ps = subprocess.check_output(
        ["ps",
         "-x",  # include processes which do not have a controlling terminal
         "-o", "pid,rss,vsz,state,command"  # show process id, resident size, virtual size, "state", and command with arguments
        ])

    lines = ps.split("\n")
    for line in lines:
        if len(line) < 1:
            continue  # Last line
        parts = line.split(None, 4)  # Only the command, which is last, can contain spaces
        if parts[0] == "PID":
            continue  # Header line

        pid = int(parts[0])
        rss = int(parts[1])
        vsz = int(parts[2])
        # process_state = parts[3]
        command = parts[4]

        # Look for firefox processes at risk of gobbling memory
        if "MacOS/firefox-bin" in command and not command.startswith("/Applications/") and "-asan-" not in command:
            # Look for ones that are actually using too much memory (multiples of 1024 bytes)
            if rss > 2*1024*1024 or vsz > 9*1024*1024:
                print "Killing: " + line
                os.kill(pid, signal.SIGKILL)


if __name__ == "__main__":
    while True:
        reapOoms()
        time.sleep(1)

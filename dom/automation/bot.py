#!/usr/bin/env python

import os
import sys

path0 = os.path.dirname(__file__)
path1 = os.path.abspath(os.path.join(path0, os.pardir, os.pardir))
sys.path.insert(0, path1)  # We must use this because this file is also called bot.py.
#sys.path.append(path1)
import bot

# RelEng uses bot.py at the original location, this file is a stub to call bot.py at the new place.

if __name__ == '__main__':
    bot.main()

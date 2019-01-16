# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Helper functions dealing with logging in funfuzz.
"""

import logging


def get_logger(name, level=logging.INFO, terminator="\n"):
    """Create a logging object and be able to tweak the terminator. Adapted from https://stackoverflow.com/a/45909663

    Args:
        name (str): Name of the logger
        level (int): Required logging level
        terminator (str): Terminator string to be appended to every line

    Returns:
        logging.Logger: Logging object
    """
    logging.getLogger("flake8").setLevel(logging.WARNING)

    logger = logging.getLogger(name)
    handler = logging.StreamHandler()
    handler.terminator = terminator
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(datefmt="[%Y-%m-%d %H:%M:%S %z]",
                                           fmt="[%(asctime)s] %(name)-8s <%(levelname)-8s> %(message)s"))
    logger.addHandler(handler)
    return logger

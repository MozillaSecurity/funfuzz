#!/usr/bin/env python
# coding=utf-8
# flake8: noqa
# pylint: disable=missing-docstring
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from setuptools import setup

if __name__ == "__main__":
    setup(name="funfuzz",
          version="0.1.0",
          entry_points={
              "console_scripts": ["funfuzz = funfuzz.bot:main"]
          },
          packages=[
              "funfuzz",
              "funfuzz.autobisectjs",
              "funfuzz.js",
              "funfuzz.util",
              "funfuzz.util.tooltool",
          ],
          package_data={"funfuzz": [
              "autobisectjs/*",
              "js/*",
              "js/jsfunfuzz/*",
              "js/shared/*",
              "util/*",
              "util/tooltool/*",
          ]},
          package_dir={"": "src"},
          zip_safe=False)

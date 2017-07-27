#!/usr/bin/env python
# coding=utf-8
# flake8: noqa
# pylint: disable=missing-docstring
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import absolute_import

from setuptools import setup

if __name__ == "__main__":
    setup(name="funfuzz",
          version="0.1.0",
          entry_points={
              "console_scripts": ["funfuzz = funfuzz:main"]
          },
          packages=[
              "funfuzz",
              "funfuzz.autobisectjs",
              "funfuzz.detect",
              "funfuzz.js",
              "funfuzz.util"
          ],
          package_data={"funfuzz": [
              "autobisectjs/*",
              "detect/*",
              "js/*",
              "util/*"
          ]},
          package_dir={"funfuzz": ""},
          zip_safe=False)

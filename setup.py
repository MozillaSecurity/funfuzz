# coding=utf-8
# pylint: disable=missing-docstring
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from setuptools import setup

if __name__ == "__main__":
    setup(name="funfuzz",
          version="0.4.0",
          entry_points={
              "console_scripts": ["funfuzz = funfuzz.bot:main"]
          },
          packages=[
              "funfuzz",
              "funfuzz.autobisectjs",
              "funfuzz.js",
              "funfuzz.util",
          ],
          package_data={"funfuzz": [
              "autobisectjs/*",
              "js/*",
              "js/jsfunfuzz/*",
              "js/shared/*",
              "util/*",
          ]},
          package_dir={"": "src"},
          install_requires=[
              "backports.print_function>=1.1.1",
              "configparser>=3.5.0",
              "future>=0.16.0",
              "FuzzManager>=0.1.3",
              "lithium-reducer>=0.2.1",
          ],
          extras_require={
              ':python_version=="2.7"': [
                  "functools32>=3.2.3",
                  "mercurial>=4.5.2",
                  "subprocess32>=3.5.0rc1",
              ]
          },
          zip_safe=False)

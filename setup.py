# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""setuptools install script"""

from setuptools import setup

EXTRAS = {
    ':python_version=="2.7"': [
        "mercurial>=4.6.2",
        "backports.tempfile>=1.0",
        "functools32>=3.2.3.post2",
        "pathlib2>=2.1.0",
        "psutil>=5.4.6",
        "subprocess32>=3.5.2",
    ],
    "test": [
        "codecov==2.0.15",
        "coverage==4.5.1",
        "flake8==3.6.0",
        "flake8-commas==2.0.0",
        "flake8-isort==2.5",
        "flake8-quotes==1.0.0",
        "isort==4.3.4",
        "pylint==1.9.3",
        "pytest==3.9.3",
        "pytest-cov==2.6.0",
        "pytest-flake8==1.0.2",
        "pytest-pylint==0.12.3",
    ]}


if __name__ == "__main__":
    setup(name="funfuzz",
          version="0.5.0a1",
          entry_points={
              "console_scripts": ["funfuzz = funfuzz.bot:main"],
          },
          packages=[
              "funfuzz",
              "funfuzz.autobisectjs",
              "funfuzz.ccoverage",
              "funfuzz.js",
              "funfuzz.util",
          ],
          package_data={"funfuzz": [
              "autobisectjs/*",
              "ccoverage/*",
              "js/*",
              "js/jsfunfuzz/*",
              "js/shared/*",
              "util/*",
          ]},
          package_dir={"": "src"},
          install_requires=[
              "backports.print_function>=1.1.1",
              "boto>=2.48.0",
              "configparser>=3.5.0",
              "future>=0.16.0",
              "requests>=2.18.4",
              "shellescape>=3.4.1",
              "whichcraft>=0.4.1",
          ],
          extras_require=EXTRAS,
          python_requires=">=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*, <4",
          zip_safe=False)

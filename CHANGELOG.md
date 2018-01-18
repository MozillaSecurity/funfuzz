## 0.4.0 (201X-XX-XX)

Features:

* TBD

Bugfixes:

* TBD

## 0.3.0 (2017-12-21)

Features:
* Basic pytest infrastructure added! - largely tests `compile_shell` for now
* Add `codecov.io` support - Now with code coverage!
* `evalInCooperativeThread` and `oomTest` are now ignored when running differential testing.

Bugfixes:
* Ripped out the `version` function from being used in jsfunfuzz
* Obsolete code removal, e.g. some flag combinations in shell_flags
* Tweaked the algorithm for the number of CPU cores used for compilation
* Miscellaneous fixes for Python stuff, linters, CI etc.

Notes:
* Minimum Mac support is now 10.11.x (El Capitan)
* Windows is still on the 0.1.x legacy branch

## 0.2.1 (2017-10-20)

Bugfixes:

* Fix Xcode 9 builds on macOS

## 0.2.0 (2017-10-18)

Features:

* First release with proper Python package folder layout structure
  * Assuming repository was cloned to `~/funfuzz`, can be installed via pip: `pip install --upgrade ~/funfuzz`

## 0.1.0 (2017-09-30)

Features:

* Legacy release with original layout structure
* Cannot be installed as a Python module
* Migrated to GitHub in July 2015 from an old Mercurial repository, created circa May 2008

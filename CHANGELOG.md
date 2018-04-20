## 0.5.0 (201X-XX-XX)

Features:

* TBD

Bugfixes:

* TBD

## 0.4.1 (2018-04-19)

Bugfixes:
* Fixed crashes in `grabCrashLog` by dealing with `str`/`unicode` types better
* Made `repos_update` not update funfuzz anymore, since [pip 10 no longer comes](https://blog.python.org/2018/04/pip-10-has-been-released.html) with a `main` method and we should not rely on the internals of pip
* Simplified `boto` import code
* Inlined platform detection code instead of relying on `subprocesses`
* Tweaked Travis / AppVeyor CI configurations

Notes:
* Windows is still on the 0.1.x legacy branch, until Python 3.5+ support is completed

## 0.4.0 (2018-04-13)

Features:
* Hit 40% test coverage! (previously 30%)
* jsfunfuzz updates
  * `async`, `for-await-of support` thanks to @arai-a
  * Obsolete functions removed (`E4X for-each`, `toSource`, `StopIteration`, `getPropertyDescriptor`, `Iterator`/`__iterator__`, `validategc` etc.)
* `tooltool` removed, along with lots of other unused functions now that `DOMFuzz` is gone
* Removed `download_build`
  * Support for bisection using downloaded builds via `autobisect` project will be added later
  * In the meantime, the existing support got removed as tinderbox builds are no longer produced by official builds
* Windows ICU library versions bumped

Bugfixes:
* Entire repository standardised to use double quotes
* Continued work towards Python 3 support, Python 3.5 is now the target
  * More fixes for unicode/str confusion when interacting with other libraries, e.g. Lithium
* Standardised name to `autobisectjs` since there is now the separate [autobisect project](https://github.com/MozillaSecurity/autobisect)
* Started using more PyPI libraries
  * e.g. `whichcraft` instead of in-house functions without tests
* `shell_flags` got rewritten
  * Added new runtime flags, e.g. `--spectre-mitigations=on`
  * Tests added
* Start moving towards the `subprocess32` PyPI library
  * En route to removing the `captureStdout` function

Platform support:
* Removed support for Mac 32-bit builds as they became obsolete everywhere
* Linux builds now require GCC 6 (official build requirement)

Notes:
* Windows is still on the 0.1.x legacy branch, until Python 3.5+ support is completed

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

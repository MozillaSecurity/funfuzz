## 0.6.0 (2019-02-19)

0.6.x supports Python 3.6+ only

Features:

* funbind: Experimental integration with binaryen landed (Linux-only) (#219)
* funbind: binaryen version bumped to 68
* jsfunfuzz: Initial support for mark bit and gray root functions, `newGlobal({newCompartment: true})`, `Object.values`, `Object.[get|set]PrototypeOf` and `enableShapeConsistencyChecks()`
* compare_jit: Ignore `Object.getOwnPropertyNames`, `dumpScopeChain`, `addMarkObservers`, `clearMarkObservers` and `getMarks`
* randorderfuzz: support streams tests
* Use exponential backoff for wasm file execution
* Add a lock using fasteners to prevent `wasm-opt` from tripping over itself
* Use exponential backoff for FuzzManager submission (#145)
* ARM64 code improvements (both simulator and native)
* ICU support bumped up to version 63
* Max gczeal value bumped up to 25
* Bump minimum macOS to be 10.13.6
* Shell builds are compiled with `--disable-cranelift` only if on [m-c rev 6fcf54117a3b](https://hg.mozilla.org/mozilla-central/rev/6fcf54117a3b) or later, till current m-c tip
* Make workaround for compiling further back, on Linux systems with sed >= 4.3 and add tests
* Use GCC for 32-bit builds when bisecting back prior to [m-c rev e1cac03485d9](https://hg.mozilla.org/mozilla-central/rev/e1cac03485d9)
* Support `--more-compartments` in most places
* `--enable-streams` has been deprecated in favour of `--no-streams`
* (all code relating to Python 2.7 support have been removed)

Bugfixes:

* funbind: Disable on ARM64 Linux due to binaryen GH issue 1615
* Fixed TypeError thrown when `file_contains_str` is run after move to Python 3.6+ (#220)
* Do not specify function names in `__init__.py` since we are now on Python 3.6+ to fix RuntimeWarning (#208)
* Remove weights in build_options for slow devices since we do not deal with those anymore
* Remove `--ion-loop-unrolling=on/off` as per [bug 1520998](https://bugzilla.mozilla.org/show_bug.cgi?id=1520998)
* Remove flags related to `--no-wasm` from compare_jit testing, replacing with new ones, e.g. `--wasm-compiler=[none|baseline|ion|baseline+ion]`
* Removed some subprocess calls in favour of the more pythonic way, e.g. for gzipping code
* Remove "-backup" file logic as its support was flaky
* Tweak packaging mode to use find_packages from setuptools in setup.py
* Windows Asan binary support fixes
* Library version bumps
* Various other bugfixes

Testing-related:

* code coverage tests added (#202)
* funfuzz now uses `pytest` throughout, old `unittest`-related code has been removed
* Switch to using `--stream` when running hg clone, on Travis
* `shellcheck` and `bashate` now run on Travis for bash scripts
* Fast tests run on Travis for macOS and Windows
* AppVeyor integration has been removed from funfuzz
* Support pylint 2.x on Python 3 (#218)
* Add cleanup script to wipe `*.pyc`, `*.pyo` files and `__pycache__` dirs, run flake8, fast pytests and pylint
* Various other Travis/testing bugfixes

## 0.5.0 (2018-11-07)

0.5.x is the final version series with stable dual Python 2/3 support, and the branch will then be put on maintenance mode. Going forward, funfuzz will be on Python 3.6+

Features:

* funfuzz: Numerous Python 3 compatibility fixes
* funfuzz: SpiderMonkey code coverage support added
* funfuzz: The `crashesat` interestingness test has been refactored to use argparse, logging and pathlib (#199)
* funfuzz: `flake8-commas`, `flake8-quotes` extensions to `flake8` linting were added
* funfuzz: There is now a `get_hg_repo.sh` script in the util directory to clone `mozilla-central` or `mozilla-beta` using aria2 instead
* funfuzz: Remove `shellify` (#184)
* funfuzz/compare_jit: `--no-streams` and `--enable-wasm-gc` are now tested
* funfuzz/compare_jit: Removed `--ion-shared-stubs=[on|off]`, `--non-writable-jitcode`, `--ion-aa=flow-sensitive` and `--ion-aa=flow-insensitive` since they are no longer part of SpiderMonkey
* jsfunfuzz: `objectEmulatingUndefined` became `createIsHTMLDDA`, see [bug 1410194](https://bugzilla.mozilla.org/show_bug.cgi?id=1410194)
* jsfunfuzz: Generates decreasing for-loops
* jsfunfuzz: Tests the `keepFailing:true` option for oomTest
* jsfunfuzz: Support `recomputeWrappers`
* jsfunfuzz: `evaluate` accepts `saveIncrementalBytecode` as a parameter, see [bug 1427860](https://bugzilla.mozilla.org/show_bug.cgi?id=1427860)
* jsfunfuzz: `newGlobal` accepts `sameCompartmentAs` as a parameter, see [bug 1487238](https://bugzilla.mozilla.org/show_bug.cgi?id=1487238)
* jsfunfuzz: `newGlobal` accepts `invisibleToDebugger` as a parameter
* jsfunfuzz: Object.prototype no longer have the `__count__` and `__parent__` properties
* jsfunfuzz: Stop generating generator expressions

Bugfixes:

* compare_jit: `--no-native-regexp` and `--no-wasm` were removed from basic_flag_sets
* compare_jit: Calling `ShellResult` in `js_interesting` would fail due to the absence of `options.jsengine`
* funfuzz: Fix #9 - compileShell fails on Fedora due to autoconf 2.13 binary name discrepancy (#189)
* funfuzz: Fix #33 - Dump the error to `.busted` log files when configuration fails, but append the info to them if they already exist
* funfuzz: Off-by-one error in path concatenation in `jsFilesIn` function fixed
* funfuzz: Some Clang/ASan build support fixes
* funfuzz: Rename `sps` to `os_ops` in loop.py (#205)
* Various other bugfixes

## 0.4.2 (2018-04-20)

Bugfixes:
*  Fix #185 - `Commandline argument -t "js" in bot.py is not recognized. But it is mentioned in the readme.md.`
*  Disable tests involving compile_shell on Python 2.7 mode unless Python 3.5+ is installed due to a mozilla-central requirement
  * This temporarily lowers code coverage numbers reported to Codecov via Travis, until Python 3.5+ support is finished
* Integrated the isort Python checker into flake8 linting process
* More automation / documentation / linting fixes

Notes:
* Windows is still on the 0.1.x legacy branch, until Python 3.5+ support is completed

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
* `evalInCooperativeThread` and `oomTest` are now ignored when running differential testing

Bugfixes:
* Ripped out the `version` function from being used in jsfunfuzz
* Obsolete code removal, e.g. some flag combinations in shell_flags
* Tweaked the algorithm for the number of CPU cores used for compilation
* Miscellaneous fixes for Python stuff, linters, CI etc

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

[![Build Status](https://travis-ci.org/MozillaSecurity/funfuzz.svg?branch=master)](https://travis-ci.org/MozillaSecurity/funfuzz) [![Build status](https://ci.appveyor.com/api/projects/status/m8gw5echa7f2f26r/branch/master?svg=true)](https://ci.appveyor.com/project/MozillaSecurity/funfuzz/branch/master)

This repository contains several JavaScript-based fuzzers. [jsfunfuzz](js/jsfunfuzz) tests JavaScript engines and can run in a JavaScript shell, compare_jit compares output from SpiderMonkey using different flags, while randorderfuzz throws in random tests from the mozilla-central directory into generated jsfunfuzz output.

Most of the code other than testcase generation is written in Python: restarting the program when it exits or crashes, noticing evidence of new bugs from the program's output, [reducing testcases](https://github.com/MozillaSecurity/lithium/), and [identifying when regressions were introduced](src/funfuzz/autobisectjs/README.md).


## Setup

Install the required pip packages using `pip install -r requirements.txt`.

Some parts of the fuzzer will only activate if the Python scripts can find your mozilla-central tree:
```
mkdir -p ~/trees/
hg clone https://hg.mozilla.org/mozilla-central/ ~/trees/mozilla-central/
```

Some parts of the harness assume a clean **Mercurial** clone of the mozilla trees. There is insufficient testing with Git for now - please file an issue if you hit problems with Git repositories of mozilla trees.

If you want to use these scripts to compile SpiderMonkey or Firefox, install the usual prerequisites for [building Firefox](https://developer.mozilla.org/en-US/docs/Mozilla/Developer_guide/Build_Instructions) or [building SpiderMonkey](https://developer.mozilla.org/en-US/docs/Mozilla/Projects/SpiderMonkey/Build_Documentation). There are [additional requirements for building with Address Sanitizer](https://developer.mozilla.org/en-US/docs/Mozilla/Testing/Firefox_and_Address_Sanitizer).

After the addition of FuzzManager support, you will need to first install the pip packages listed in requirements.txt of [FuzzManager](https://github.com/MozillaSecurity/FuzzManager).

Here's a guide to [pip and virtualenv](https://www.dabapps.com/blog/introduction-to-pip-and-virtualenv-python/).

### Windows (only 64-bit supported)

1. Install [MozillaBuild](https://wiki.mozilla.org/MozillaBuild) (Using compile_shell for SpiderMonkey requires at least version 3.0).
2. Install [Git for Windows](https://msysgit.github.io/) to get Git for Windows in order to clone these funfuzz repositories. (32-bit works best for now)
3. Install [Debugging Tools for Windows](https://msdn.microsoft.com/en-us/windows/hardware/hh852365.aspx) to get cdb.exe and thus stacks from crashes.
4. Make sure you install at least Microsoft Visual Studio 2015 (Community Edition is recommended) as per the build instructions above in the Setup section. Visual Studio 2017 is preferred.
5. Run `start-shell.bat` to get a MSYS shell. Do not use the MSYS shell that comes with Git for Windows. You can use Git by calling its absolute path, e.g. `/c/Program\ Files/Git/bin/git.exe`.
    1. Run the batch file with administrator privileges to get gflags analysis working correctly.


### Mac

1. If you encounter problems accessing the compiler, try re-running this command:

  ```xcode-select --install```

especially after updating major/minor OS versions. This sometimes manifests on Mac OS X Combo updates.

2. Install LLVM via Homebrew, to get llvm-symbolizer needed for symbolizing ASan crash stacks.

  ```
  brew install llvm
  ```


### Linux

1. To ensure your core dumps don't get mixed up when multiple instances crash at the same time, run:

  ```
  echo -n 1 | sudo tee /proc/sys/kernel/core_uses_pid
  ```
2. Install 32-bit libraries to compile 32-bit binaries:
  * Debian/Ubuntu: ```sudo apt-get install lib32z1 gcc-multilib g++-multilib```
  * Fedora: (Fedora is known to work, however the exact library names are unknown for now.)
  ** Note that parts of the code which contain ```if isLinux and float(platform.linux_distribution()[1]) > 15.04``` might fail on Fedora, as they assume Ubuntu's versioning scheme. Patches welcome.
3. Install gdb:
  * Debian/Ubuntu: ```sudo apt-get install gdb```
  * Fedora: Please ensure that all development packages are installed (see ```rpm -qa "*devel"```), and run ```yum install gdb```
4. Install clang for clang/ASan builds:
  * Debian/Ubuntu: ```sudo apt-get install clang```


## Running funfuzz

To run **only the js fuzzers** which compiles shells with random configurations every 8 hours and tests them:

`python -u funfuzz.loop_bot -b "--random" -t "js" --target-time 28800 | tee ~/log-loop_botPy.txt`

To test **a patch** (assuming patch is in `~/patch.diff`) against a specific branch (assuming **Mercurial** mozilla-inbound is in `~/trees/mozilla-inbound`), using a debug 64-bit deterministic shell configuration, every 8 hours:

`python -u funfuzz.loop_bot -b "--enable-debug --enable-more-deterministic -R ~/trees/mozilla-inbound -P ~/patch.diff" -t "js" --target-time 28800 | tee ~/log-loop_botPy.txt`

In js mode, loop_bot makes use of:

* [compile_shell](js/compile_shell.py)
* [jsfunfuzz](src/funfuzz/js/jsfunfuzz)
* [compare_jit](src/funfuzz/js/compare_jit.py) (if testing deterministic builds)
* randorderfuzz (included in funfuzz, if tests are present in the mozilla repository)
* [autoBisect](src/funfuzz/autobisectjs/README.md) (if the mozilla repository is present).

The parameters in `-b` get passed into [compile_shell](js/compile_shell.py) and [autoBisect](src/funfuzz/autobisectjs/README.md).

You will also need to need a `~/.fuzzmanagerconf` file, similar to:

```
[Main]
serverhost = <your hostname>
serverport = <your port>
serverproto = https
serverauthtoken = <if any>
sigdir = /Users/<your username>/sigcache/
tool = jsfunfuzz
```

Replace anything between `<` and `>` with your desired parameters.

## FAQ:

**Q: What platforms does funfuzz run on?**

**A:** compile_shell has been tested on:

* Windows 10 and 7, with [MozillaBuild 3.0](https://wiki.mozilla.org/MozillaBuild). It should also work with Windows Server 2012 R2.
* Mac OS X 10.13
* Ubuntu 16.04 LTS and later
  * Note: We may try to make this work on Ubuntu 14.04 LTS (via Travis)

Fedora Linux has not been tested extensively and there may be a few bugs along the way.

The following operating systems are old or less common and while they may still work, be prepared to **expect issues** along the way:

* Windows Vista / Windows 8 / Windows 8.1
* Mac OS X 10.10 through 10.12
* Ubuntu Linux 15.10 and prior (see note above about 14.04 LTS)
* Ubuntu (and variants) on [ARM ODROID boards](http://www.hardkernel.com/main/main.php)

Support for the following operating systems **have been removed**:

* Windows XP
* Mac OS X 10.6 through 10.9

**Q: What version of Python does funfuzz require?**

**A:** We recommend the Python 2.7.x series. There is no support for Python 3 yet, although there is work happening for the move to Python 3.

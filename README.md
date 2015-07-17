This repository contains two JavaScript-based fuzzers. [jsfunfuzz](js) tests JavaScript engines and can run in a JavaScript shell. [DOMFuzz](dom) tests layout and other parts of browser engines through DOM API calls.

Most of the code other than testcase generation is written in Python: restarting the program when it exits or crashes, noticing evidence of new bugs from the program's output, [reducing testcases](https://github.com/MozillaSecurity/lithium/), and [identifying when regressions were introduced](autobisect-js).


## Setup

Check out the **[lithium](https://github.com/MozillaSecurity/lithium/)** and **[FuzzManager](https://github.com/MozillaSecurity/FuzzManager)** repositories side-by-side by this one.

Some parts of the fuzzer will only activate if the Python scripts can find your mozilla-central tree:
```
mkdir -p ~/trees/
hg clone https://hg.mozilla.org/mozilla-central/ ~/trees/mozilla-central/
```

Some parts of the harness assume a clean **Mercurial** clone of the mozilla trees. There is insufficient testing with Git for now - please file an issue if you hit problems with Git repositories of mozilla trees.

If you want to use these scripts to compile SpiderMonkey or Firefox, install the usual prerequisites for [building Firefox](https://developer.mozilla.org/en-US/docs/Mozilla/Developer_guide/Build_Instructions) or [building SpiderMonkey](https://developer.mozilla.org/en-US/docs/Mozilla/Projects/SpiderMonkey/Build_Documentation). There are [additional requirements for building with Address Sanitizer](https://developer.mozilla.org/en-US/docs/Mozilla/Testing/Firefox_and_Address_Sanitizer).


### Windows

1. Install [MozillaBuild](https://wiki.mozilla.org/MozillaBuild) (Using compileShell for SpiderMonkey requires at least version 2.0.0) to get an msys shell.
2. Install [Git for Windows](https://msysgit.github.io/) to get Git for Windows in order to clone these funfuzz repositories.
3. Install [Debugging Tools for Windows](https://msdn.microsoft.com/en-us/windows/hardware/hh852365.aspx) to get cdb.exe and thus stacks from crashes.


### Mac

1. On Mac OS X 10.9, you must first install a newer version of unzip than the one that comes with the OS. (Old versions [hit an error](https://bugzilla.mozilla.org/show_bug.cgi?id=1032391) on large zip files, such as the "mac64.tests.zip" file that [downloadBuild.py](util/downloadBuild.py) grabs.)

  ```
  brew install homebrew/dupes/unzip
  brew link --force unzip
  ```

2. If you encounter problems accessing the compiler, try re-running this command:

  ```xcode-select --install```

especially after updating major/minor OS versions. This sometimes manifests on Mac OS X Combo updates.


### Linux

1. To ensure your core dumps don't get mixed up when multiple instances crash at the same time, run:

  ```
  echo -n 1 | sudo tee /proc/sys/kernel/core_uses_pid
  ```
2. Install 32-bit libraries to compile 32-bit binaries:
  * Debian/Ubuntu: ```sudo apt-get install lib32z1 gcc-multilib g++-multilib```
  * Fedora: (Fedora is known to work, however the exact library names are unknown for now.)
3. Install gdb:
  * Debian/Ubuntu: ```sudo apt-get install gdb```
  * Fedora: ???

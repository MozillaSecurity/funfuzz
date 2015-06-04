This repository contains two JavaScript-based fuzzers. [jsfunfuzz](js) tests JavaScript engines and can run in a JavaScript shell. [DOMFuzz](dom) tests layout and other parts of browser engines through DOM API calls.

Most of the code other than testcase generation is written in Python: restarting the program when it exits or crashes, noticing evidence of new bugs from the program's output, [reducing testcases](https://github.com/MozillaSecurity/lithium/), and [identifying when regressions were introduced](autobisect-js).


## Setup

Check out the [lithium](https://github.com/MozillaSecurity/lithium/) and [FuzzManager](https://github.com/MozillaSecurity/FuzzManager) repositories side-by-side by this one.

Some parts of the fuzzer will only activate if the Python scripts can find your mozilla-central tree:
```
mkdir -p ~/trees/
hg clone https://hg.mozilla.org/mozilla-central/ ~/trees/mozilla-central/
```

If you want to use these scripts to compile SpiderMonkey or Firefox, install the usual prerequisistes for [building Firefox](https://developer.mozilla.org/en-US/docs/Mozilla/Developer_guide/Build_Instructions) or [building SpiderMonkey](https://developer.mozilla.org/en-US/docs/Mozilla/Projects/SpiderMonkey/Build_Documentation). There are [additional requirements for building with Address Sanitizer](https://developer.mozilla.org/en-US/docs/Mozilla/Testing/Firefox_and_Address_Sanitizer).


### Windows

Install [MozillaBuild](https://wiki.mozilla.org/MozillaBuild) to get an msys shell.


### Mac

On Mac OS X 10.9, you must first install a newer version of unzip than the one that comes with the OS. (Old versions [hit an error](https://bugzilla.mozilla.org/show_bug.cgi?id=1032391) on large zip files, such as the "mac64.tests.zip" file that [downloadBuild.py](util/downloadBuild.py) grabs.)

```
brew install homebrew/dupes/unzip
brew link --force unzip
```


## Linux

To ensure your core dumps don't get mixed up when multiple instances crash at the same time, run:
```
echo -n 1 | sudo tee /proc/sys/kernel/core_uses_pid
```

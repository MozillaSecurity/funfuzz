DOMFuzz tests layout and other parts of browser engines through DOM API calls. Some [modules](fuzzer/modules/) lean more toward "mutation" and others lean more toward "generation", but all act on the DOM of a web page.

For each instance of Firefox, up to 4 modules will be chosen and enabled. Modules include:
* [Stir DOM](fuzzer/modules/stir-dom.js), which moves nodes around the document tree using appendChild and insertBefore.
* [Random Styles](fuzzer/modules/style-properties.js), which adds inline style properties.


## Setup

### Mac

When fuzzing a browser, you may want to disable GUI crash dialogs. You'll still get crash reports in `/Library/Logs/DiagnosticReports/` and `~/Library/Logs/DiagnosticReports/`, but they won't be shown on-screen or submitted to Apple.

```
defaults write com.apple.CrashReporter DialogType server
```

## Running

Running `./loopdomfuzz.py build` will:
* Figure out which version of Firefox you are testing and use appropriate ignore lists.
* Create temporary Firefox profiles with the [DOMFuzz Helper extension](extension/) installed, [appropriate settings](automation/constant-prefs.js), and some [random settings](automation/randomPrefs.py) as well.
* In a loop, open Firefox to a random file from the reftest suite, and load random DOMFuzz modules into it. (If a bug is found, it will place a file in a wtmp*/ directory, and try to reduce it with Lithium.)

|build| must be a directory containing a build of Firefox:
* A Firefox object directory, built locally with --enable-tests
* A Treeherder build that was downloaded using funfuzz/util/downloadBuild.py

Quick start:
```
funfuzz/util/downloadBuild.py && funfuzz/util/multi.py 8 funfuzz/dom/automation/loopdomfuzz.py build
```


## Contributors

* Paul Nickerson contributed a module for testing CanvasRenderingContext2D and prototyped serializeDOMAsScript
* Christoph Diehl contributed a bunch of modules
* Mats Palmgren contributed [Stir Tables](fuzzer/modules/tables.js)

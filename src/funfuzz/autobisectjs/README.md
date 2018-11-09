autobisectjs will help you to find out when a changeset introduced problems. It can also point at a changeset that may have exposed the issue.

It helps with work allocation:

* The engineer that most recently worked on the code is the one most likely to know how to fix the bug.
* If not, the engineer may be able to forward to someone more knowledgeable.

## Find changeset that introduced problems using autobisectjs

For SpiderMonkey, use the following while compiling locally:

`<python executable> -m funfuzz.autobisectjs -p "--fuzzing-safe --no-threads --ion-eager testcase.js" -b "--enable-debug --enable-more-deterministic"`

assuming the testcase requires "--fuzzing-safe --no-threads --ion-eager" as runtime flags.

This will take about:

* **45 - 60 minutes** on a relatively recent powerful computer on Linux / Mac
  * assuming each compilation takes about 3 minutes
  * we should be able to find the problem within 16+ tests.
* **2 hours** on Windows
  * where each compilation is assumed to take 6 minutes.

If you have an internet connection, and the testcase causes problems with:

* a [downloaded js shell](https://archive.mozilla.org/pub/mozilla.org/firefox/tinderbox-builds/mozilla-central-macosx64-debug/latest/jsshell-mac64.zip)
* these problems started happening within the last month

you can try bisecting using downloaded builds:

`<python executable> -m funfuzz.autobisectjs -p "--fuzzing-safe --no-threads --ion-eager testcase.js" -b "--enable-debug" -T`

This should take < 5 minutes total assuming a fast internet connection, since it does not need to compile shells.

Refer to [compile_shell documentation](../js/README.md) for parameters to be passed into "-b".

## Examples

To try this yourself, run the following commands with the testcases from the bug numbers pasted into the file, e.g. "1188586.js" contains the testcase from [bug 1188586](https://bugzilla.mozilla.org/show_bug.cgi?id=1188586).

* To test when a bug was introduced by **downloading mozilla-inbound builds** from Mozilla:

```funfuzz/autobisect-js/autoBisect.py -p "--fuzzing-safe --no-threads --ion-eager 1188586.js" -b "--enable-debug" -T```

However, this only works effectively if the bug was recent, because builds are only stored per-push within the past month.

* The equivalent command using **local compiled builds** is:

```funfuzz/autobisect-js/autoBisect.py -p "--fuzzing-safe --no-threads --ion-eager 1188586.js" -b "--enable-debug --enable-more-deterministic --enable-nspr-build"```

* To **test branches**, e.g. on mozilla-inbound instead (or any other release branch including ESR), assuming the *Mercurial* repository is cloned to "~/trees/mozilla-inbound":

```funfuzz/autobisect-js/autoBisect.py -p "--fuzzing-safe --no-threads --ion-eager 1188586.js" -b "--enable-debug --enable-more-deterministic --enable-nspr-build -R ~/trees/mozilla-inbound"```

* During bisection, perhaps the testcase used to crash in the past; however we are only interested in the assertion failure. You can make autoBisect look out for the **assertion failure message**:

```funfuzz/autobisect-js/autoBisect.py -p "--fuzzing-safe --no-threads --ion-eager 1188586.js" -b "--enable-debug --enable-more-deterministic --enable-nspr-build" -o "Assertion failure"```

* To look out for a particular **exit code**, use "-w":

```funfuzz/autobisect-js/autoBisect.py -p "--fuzzing-safe --no-threads --ion-eager 1189137.js" -b "--enable-debug --enable-more-deterministic --enable-nspr-build" -w 3```

* To specify **starting and ending revisions**, use "-s" and "-e":

```funfuzz/autobisect-js/autoBisect.py -s 7820fd141998 -e 'parents(322487136b28)' -p "--no-threads --ion-eager --unboxed-objects 1189137.js" -b "--enable-debug --enable-more-deterministic --enable-nspr-build" -o "Assertion failed"```

This method can be used to find when a regression was introduced as well as when a bug got fixed.

* Or, the testcase is **intermittent** and only reproduces once every 5 tries. autoBisect can be set to use the "range" interestingness test to retest 50 times before concluding if it is interesting or not:

```funfuzz/autobisect-js/autoBisect.py -p "--fuzzing-safe --no-threads --ion-eager 1188586.js" -b "--enable-debug --enable-more-deterministic --enable-nspr-build" -i range 1 50 crashes --timeout=3```

Note that this requires the [lithium repository](https://github.com/MozillaSecurity/lithium) to be cloned adjacent to the funfuzz repository.

You could specify the assertion message this way too:

```funfuzz/autobisect-js/autoBisect.py -p "--fuzzing-safe --no-threads --ion-eager 1188586.js" -b "--enable-debug --enable-more-deterministic --enable-nspr-build" -i range 1 50 outputs --timeout=3 'Assertion failure'```

"-i" should be the last argument on the command line.

* To bisect **bugs found by compareJIT**:

```funfuzz/autobisect-js/autoBisect.py -s 6ec4eb9786d8 -p 1183423.js -b "--enable-debug --enable-more-deterministic --enable-nspr-build -R ~/trees/mozilla-central" -i ~/funfuzz/js/compareJIT.py --minlevel=6 mozilla-central```

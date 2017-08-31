autoBisect will help you to find out when a changeset introduced problems. It can also point at a changeset that may have exposed the issue.

It helps with work allocation:

* The engineer that most recently worked on the code is the one most likely to know how to fix the bug.
* If not, the engineer may be able to forward to someone more knowledgeable.

## Find changeset that introduced problems using autoBisect

For SpiderMonkey, use the following while compiling locally:

`funfuzz/autobisectjs/autoBisect.py -p "--fuzzing-safe --no-threads --ion-eager testcase.js" -b "--enable-debug --enable-more-deterministic"`

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

`funfuzz/autobisectjs/autoBisect.py -p "--fuzzing-safe --no-threads --ion-eager testcase.js" -b "--enable-debug" -T`

This should take < 5 minutes total assuming a fast internet connection, since it does not need to compile shells.

Refer to [compileShell.py documentation](../js/README.md) for parameters to be passed into "-b".

```
Usage: autoBisect.py [options]

Options:
  -h, --help            show this help message and exit
  -b BUILDOPTIONS, --build=BUILDOPTIONS
                        Specify js shell build options, e.g. -b "--enable-
                        debug --32" (python buildOptions.py --help)
  --resetToTipFirst     First reset to default tip overwriting all local
                        changes. Equivalent to first executing `hg update -C
                        default`. Defaults to "False".
  -s STARTREPO, --startRev=STARTREPO
                        Earliest changeset/build numeric ID to consider
                        (usually a "good" cset). Defaults to the earliest
                        revision known to work at all/available.
  -e ENDREPO, --endRev=ENDREPO
                        Latest changeset/build numeric ID to consider (usually
                        a "bad" cset). Defaults to the head of the main
                        branch, "default", or latest available build.
  -k, --skipInitialRevs
                        Skip testing the -s and -e revisions and automatically
                        trust them as -g and -b.
  -o OUTPUT, --output=OUTPUT
                        Stdout or stderr output to be observed. Defaults to
                        "". For assertions, set to "ssertion fail"
  -w WATCHEXITCODE, --watchExitCode=WATCHEXITCODE
                        Look out for a specific exit code. Only this exit code
                        will be considered "bad".
  -i, --useInterestingnessTests
                        Interpret the final arguments as an interestingness
                        test.
  -p PARAMETERS, --parameters=PARAMETERS
                        Specify parameters for the js shell, e.g. -p "-a
                        --ion-eager testcase.js".
  -l COMPILATIONFAILEDLABEL, --compilationFailedLabel=COMPILATIONFAILEDLABEL
                        Specify how to treat revisions that fail to compile.
                        (bad, good, or skip) Defaults to "skip"
  -T, --useTreeherderBinaries
                        Use treeherder binaries for quick bisection, assuming
                        a fast internet connection. Defaults to "False"
  -N NAMEOFTREEHERDERBRANCH, --nameOfTreeherderBranch=NAMEOFTREEHERDERBRANCH
                        Name of the branch to download. Defaults to "mozilla-
                        inbound"
```

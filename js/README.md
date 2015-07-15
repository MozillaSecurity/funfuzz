## Compile SpiderMonkey using compileShell

To compile a SpiderMonkey shell, run:

`funfuzz/js/compileShell.py -b "--enable-debug --enable-more-deterministic --enable-nspr-build -R ~/trees/mozilla-central"`

in order to get a debug deterministic 64-bit shell with NSPR compiled, off the **Mercurial** repository located at ~/trees/mozilla-central.

The options accepted by -b are also available via funfuzz/js/buildOptions.py:

```
  --random              Chooses sensible random build options. Defaults to
                        "False".
  -R REPODIR, --repoDir REPODIR
                        Sets the source repository.
  -P PATCHFILE, --patch PATCHFILE
                        Define the path to a single JS patch. Ensure mq is
                        installed.
  --32                  Build 32-bit shells, but if not enabled, 64-bit shells
                        are built.
  --enable-debug        Build shells with --enable-debug. Defaults to "False".
  --disable-debug       Build shells with --disable-debug. Defaults to
                        "False".
  --enable-optimize     Build shells with --enable-optimize. Defaults to
                        "False".
  --disable-optimize    Build shells with --disable-optimize. Defaults to
                        "False".
  --enable-profiling    Build shells with --enable-profiling. Defaults to
                        "False".
  --build-with-asan     Build with clang AddressSanitizer support. Defaults to
                        "False".
  --build-with-valgrind
                        Build with valgrind.h bits. Defaults to "False".
                        Requires --enable-hardfp for ARM platforms.
  --run-with-valgrind   Run the shell under Valgrind. Requires --build-with-
                        valgrind.
  --enable-nspr-build   Build the shell using (in-tree) NSPR. This is the
                        default on Windows. On POSIX platforms, shells default
                        to --enable-posix-nspr-emulation. Using --enable-nspr-
                        build creates a JS shell that is more like the
                        browser. Defaults to "False".
  --enable-more-deterministic
                        Build shells with --enable-more-deterministic.
                        Defaults to "False".
  --enable-simulator=arm
                        Build shells with --enable-simulator=arm, only
                        applicable to 32-bit shells. Defaults to "False".
  --enable-simulator=arm64
                        Build shells with --enable-simulator=arm64, only
                        applicable to 64-bit shells. Defaults to "False".
```

## Running jsfunfuzz

To test an existing SpiderMonkey shell called `./js`, run:

`funfuzz/js/loopjsfunfuzz.py --random-flags --comparejit 20 mozilla-central ./js`

* `--random-flags` tells it to use [shellFlags.py](shellFlags.py) to
* `--comparejit` tells it to run [compareJIT.py](compareJIT.py) on most of the generated code, detecting bugs where adding optimization flags like --ion-eager changes the output.
* `20` tells it to kill any instance that runs for more than 20 seconds
* `mozilla-central` tells it to use the known-bugs lists (for assertions and crashes) in [known/mozilla-central/](../known/mozilla-central/).

If loopjsfunfuzz detects a new bug, it will run [Lithium](https://github.com/MozillaSecurity/lithium/) to reduce the testcase. It will call Lithium with either [jsInteresting.py](jsInteresting.py) or [compareJIT.py](compareJIT.py) as the "interestingness test".

Using [bot.py](../bot.py) --test-type=js, you can automate downloading or building new versions of the SpiderMonkey shell, and running several instances of loopjsfunfuzz.py for parallelism.


## What jsfunfuzz does

*jsfunfuzz* creates random JavaScript function bodies (including invalid ones) to test many parts of JavaScript engines.

The largest module of jsfunfuzz is [gen-grammar.js](jsfunfuzz/gen-grammar.js).  thinking loosely in terms of "statements", "expressions", "lvalues", "literals", etc. It's almost a context-free grammar fuzzer... |cat| and |totallyRandom| especially make it seem like one.

Once it creates a function body, it does the following things with it:
* Splits it in half and tries to compile each half, mostly to find bugs in the compiler's error-handling.
* Compiles it
* Executes it
* If executing returned a generator, loops through the generator.

## Contributors

* [Jesse Ruderman](https://twitter.com/jruderman) wrote most of the fuzzer
* [Gary Kwong](https://twitter.com/nth10sd) wrote a lot of the Python
* [Christian Holler](https://twitter.com/mozdeco) improved the compilation scripts
* [Jan de Mooij](https://twitter.com/jandemooij) prototyped [stress-testing objects and PICs](https://bugzilla.mozilla.org/show_bug.cgi?id=6309960)
* [David Keeler](https://twitter.com/mozkeeler) modified the regular expression generator to also generate (almost-)matching strings, based on an idea from [Oliver Hunt](https://twitter.com/ohunt).
* [The SpiderMonkey team](https://twitter.com/SpiderMonkeyJS) fixed over 2000 of our bugs, so we could keep fuzzing!

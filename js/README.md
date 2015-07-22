## Compile SpiderMonkey using compileShell

To compile a SpiderMonkey shell, run:

`funfuzz/js/compileShell.py -b "--enable-debug --enable-more-deterministic --enable-nspr-build -R ~/trees/mozilla-central"`

in order to get a debug 64-bit deterministic shell with NSPR compiled, off the **Mercurial** repository located at ~/trees/mozilla-central.

Clone the repository to that location using:

`hg clone https://hg.mozilla.org/mozilla-central/ ~/trees/mozilla-central`

assuming the ~/trees folder is created and present.

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


### More examples:

To compile a debug 64-bit deterministic shell used for profiling, do:

`funfuzz/js/compileShell.py -b "--enable-debug --enable-more-deterministic --enable-nspr-build -R ~/trees/mozilla-central"`

To compile an optimized 32-bit shell, do:

`funfuzz/js/compileShell.py -b "--32 --enable-optimize --enable-nspr-build -R ~/trees/mozilla-central"`

By default, js should compile an optimized shell even without --enable-optimize explicitly specified.

To compile a debug 32-bit ARM-simulator shell, do:

`funfuzz/js/compileShell.py -b "--32 --enable-debug --enable-nspr-build --enable-simulator=arm -R ~/trees/mozilla-central"`

To compile a debug 64-bit shell with AddressSanitizer (ASan) support, do:

`funfuzz/js/compileShell.py -b "--enable-debug --enable-nspr-build --build-with-asan -R ~/trees/mozilla-central"`

Note that this uses git to clone a specific known working revision of LLVM into `~/llvm`, compiles it, then uses this specific revision to compile SpiderMonkey.

To compile an optimized 64-bit shell with Valgrind support, do:

`funfuzz/js/compileShell.py -b "--enable-optimize --enable-nspr-build --build-with-valgrind -R ~/trees/mozilla-central"`

To test a patch with a debug 64-bit deterministic shell, do:

`funfuzz/js/compileShell.py -b "--enable-debug --enable-more-deterministic --enable-nspr-build -R ~/trees/mozilla-central -P <path to patch>"`

Note that this **requires mq to be activated** in Mercurial and assumes that there are **no patches** in the patch queue.

To compile a debug 64-bit deterministic shell from a specific mozilla-central revision, do:

`funfuzz/js/compileShell.py -b "--enable-debug --enable-more-deterministic --enable-nspr-build -R ~/trees/mozilla-central" -r <mercurial revision hash>`


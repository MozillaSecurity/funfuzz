## Compile SpiderMonkey using compileShell

To compile a SpiderMonkey shell, run:

`funfuzz/js/compileShell.py -b "--enable-debug --enable-more-deterministic -R ~/trees/mozilla-central"`

in order to get a debug 64-bit deterministic shell, off the **Mercurial** repository located at ~/trees/mozilla-central.

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
                        Currently defaults to True in configure.in on mozilla-
                        central.
  --disable-debug       Build shells with --disable-debug. Defaults to
                        "False". Currently defaults to True in configure.in on
                        mozilla-central.
  --enable-optimize     Build shells with --enable-optimize. Defaults to
                        "False".
  --disable-optimize    Build shells with --disable-optimize. Defaults to
                        "False".
  --enable-profiling    Build shells with --enable-profiling. Defaults to
                        "False". Currently defaults to True in configure.in on
                        mozilla-central.
  --disable-profiling   Build with profiling off. Defaults to "True" on Linux,
                        else "False".
  --build-with-clang    Build with clang. Defaults to "True" on Macs, "False"
                        otherwise.
  --build-with-asan     Build with clang AddressSanitizer support. Defaults to
                        "False".
  --build-with-valgrind
                        Build with valgrind.h bits. Defaults to "False".
                        Requires --enable-hardfp for ARM platforms.
  --run-with-valgrind   Run the shell under Valgrind. Requires --build-with-
                        valgrind.
  --enable-more-deterministic
                        Build shells with --enable-more-deterministic.
                        Defaults to "False".
  --enable-oom-breakpoint
                        Build shells with --enable-oom-breakpoint. Defaults to
                        "False".
  --without-intl-api    Build shells using --without-intl-api. Defaults to
                        "False".
  --enable-simulator=arm
                        Build shells with --enable-simulator=arm, only
                        applicable to 32-bit shells. Defaults to "False".
  --enable-simulator=arm64
                        Build shells with --enable-simulator=arm64, only
                        applicable to 64-bit shells. Defaults to "False".
  --enable-arm-simulator
                        Build the shell using --enable-arm-simulator for
                        legacy purposes. This flag is obsolete and is the
                        equivalent of --enable-simulator=arm, use --enable-
                        simulator=[arm|arm64] instead. Defaults to "False".
```

## Additional information
* compileShell
  * [More examples](examples-compileShell.md)
  * [FAQ](faq-compileShell.md)

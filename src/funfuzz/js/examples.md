### Examples:

* To compile a debug 64-bit deterministic shell, do:

`<python executable> -m funfuzz.js.compile_shell -b "--enable-debug --enable-more-deterministic -R ~/trees/mozilla-central"`

* To compile an optimized 32-bit shell, do:

`<python executable> -m funfuzz.js.compile_shell -b "--32 --enable-optimize -R ~/trees/mozilla-central"`

By default, js should compile an optimized shell even without --enable-optimize explicitly specified.

* To compile a debug 32-bit ARM-simulator shell, do:

`<python executable> -m funfuzz.js.compile_shell -b "--32 --enable-debug --enable-simulator=arm -R ~/trees/mozilla-central"`

* To compile a debug 64-bit shell with AddressSanitizer (ASan) support, do:

`<python executable> -m funfuzz.js.compile_shell -b "--enable-debug --enable-address-sanitizer -R ~/trees/mozilla-central"`

Note that this uses git to clone a specific known working revision of LLVM into `~/llvm`, compiles it, then uses this specific revision to compile SpiderMonkey.

* To compile an optimized 64-bit shell with Valgrind support, do:

`<python executable> -m funfuzz.js.compile_shell -b "--enable-optimize --enable-valgrind -R ~/trees/mozilla-central"`

* To test a patch with a debug 64-bit deterministic shell, do:

`<python executable> -m funfuzz.js.compile_shell -b "--enable-debug --enable-more-deterministic -R ~/trees/mozilla-central -P <path to patch>"`

Note that this **requires mq to be activated** in Mercurial and assumes that there are **no patches** in the patch queue.

* To compile a debug 64-bit deterministic shell from a specific mozilla-central revision, do:

`<python executable> -m funfuzz.js.compile_shell -b "--enable-debug --enable-more-deterministic -R ~/trees/mozilla-central" -r <mercurial revision hash>`


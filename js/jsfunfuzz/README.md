*jsfunfuzz* creates random JavaScript function bodies (including invalid ones) to test many parts of JavaScript engines.

The largest module of jsfunfuzz is [gen-grammar.js](jsfunfuzz/gen-grammar.js).  thinking loosely in terms of "statements", "expressions", "lvalues", "literals", etc. It's almost a context-free grammar fuzzer... |cat| and |totallyRandom| especially make it seem like one.

Once it creates a function body, it does the following things with it:
* Splits it in half and tries to compile each half, mostly to find bugs in the compiler's error-handling.
* Compiles it
* Executes it
* If executing returned a generator, loops through the generator.


## Running jsfunfuzz

To test an existing SpiderMonkey shell called `./js`, run:

`funfuzz/js/loopjsfunfuzz.py --random-flags --comparejit 20 mozilla-central ./js`

* `--random-flags` tells it to use [shellFlags.py](shellFlags.py) to
* `--comparejit` tells it to run [compareJIT.py](compareJIT.py) on most of the generated code, detecting bugs where adding optimization flags like --ion-eager changes the output.
* `20` tells it to kill any instance that runs for more than 20 seconds
* `mozilla-central` tells it to use the known-bugs lists (for assertions and crashes) in [known/mozilla-central/](../known/mozilla-central/).

If loopjsfunfuzz detects a new bug, it will run [Lithium](https://github.com/MozillaSecurity/lithium/) to reduce the testcase. It will call Lithium with either [jsInteresting.py](jsInteresting.py) or [compareJIT.py](compareJIT.py) as the "interestingness test".

Using [bot.py](../bot.py) --test-type=js, you can automate downloading or building new versions of the SpiderMonkey shell, and running several instances of loopjsfunfuzz.py for parallelism.

Through randorderfuzz, if the harness detects tests in the mozilla-central tree, it may load or incorporate tests into its fuzzing input in a random order.


## Contributors

* [Jesse Ruderman](https://twitter.com/jruderman) wrote most of the fuzzer
* [Gary Kwong](https://twitter.com/nth10sd) wrote a lot of the Python
* [Christian Holler](https://twitter.com/mozdeco) improved the compilation scripts
* [Jan de Mooij](https://twitter.com/jandemooij) prototyped [stress-testing objects and PICs](https://bugzilla.mozilla.org/show_bug.cgi?id=6309960)
* [David Keeler](https://twitter.com/mozkeeler) modified the regular expression generator to also generate (almost-)matching strings, based on an idea from [Oliver Hunt](https://twitter.com/ohunt).
* [The SpiderMonkey team](https://twitter.com/SpiderMonkeyJS) fixed over 2000 of our bugs, so we could keep fuzzing!

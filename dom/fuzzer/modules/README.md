When DOMFuzz starts on a page, [main.js](../main.js) will choose a subset of modules to enable. The enabled modules will have their makeCommand functions called many times.


### makeCommand functions

makeCommand should return a snippet of JavaScript to be used as the body of a function. It can also return a small array of related snippets (e.g. statements) that Lithium might be able to whittle down.

makeCommand should be free of side-effects on the DOM.  (Side-effects on the fuzzer's own data structures are ok, and side-effects on the random number generator are expected.)  This helps ensure that the recorded sequence of actions will match the initial sequence.

The effect of the generated commands (on the DOM) must not depend on the state of the random number generator.  The random number generator will be in a different state during playback of a recorded fuzzCommands array, because makeCommand isn't called then.  (Again, side-effects on fuzzer data structures and on the random number generator are ok.)


### Weight

A module's weight should be chosen based on:

* The quantity and severity of bugs you expect it to find
* How frustrating it is to reduce bugs it finds
* Speed

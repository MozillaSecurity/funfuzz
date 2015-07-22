This document assumes you found a bug with the DOM fuzzer and want to make a reduced testcase.

Browser engine developers appreciate reduced testcases, because they are easier to understand and stable over time. They can often add these tests directly to regression test suites, ensuring the bug doesn't resurface and giving your fuzzer a new starting point (if you use the test suite as a corpus).


## Reduce the fuzzCommands array

[loopdomfuzz.py](automation/loopdomfuzz.py) creates testcases in a format that lets Lithium reduce them:

```
var fuzzCommands = [
  // DDBEGIN
  { note: 101,    fun: function() { ... } },
  { note: 102,    fun: function() { ... } },
  ...
  // DDEND
  { note: 'done', rest: true },
  { note: 'quit', fun: function() { fuzzPriv.quitApplication(); } },
];
```

The ``DDBEGIN`` and ``DDEND`` markers tell Lithium what part of the file to reduce, and the `quitApplication` call tells Firefox to exit after running the scripts. loopdomfuzz.py calls Lithium once. If you change the testcase in a way that should un-stick Lithium, you can run Lithium again with the same options (typically `lithium.py domInteresting.py build testcase.html`).


## Reducing layout testcases

For testcases that consist of basic DOM Core calls (createElement, appendChild) and CSS, it's usually possible to transform the testcase into something simple and mostly-static.

### Try simplifying transformations

If the page contains...     | Try replacing it with...
-----------------------     | ------------------------
Accented characters         | 'x'
Chinese characters          | ' x ' (the whitespace lets it wrap)
<small>                     | <span> or <span style="font-size: smaller">
Canvas with no drawing      | <div style="inline-block; width: 300px; height: 150px;">
-moz-appearance             | smallish width and height
Percentage widths           | Pixel widths (find them using computed styles)
No doctype                  | <!DOCTYPE html>, plus rules from [quirk.css](https://dxr.mozilla.org/mozilla-central/source/layout/style/quirk.css) if needed
{ rest: true }              | { fun: function() { document.documentElement.offsetHeight; } }

### Try to reduce dynamism

Often, it's only necessary for the last appendChild or removeChild call to be dynamic; the rest of the testcase can be markup. If you're having trouble figuring out how much of the testcase needs to be dynamic, inserting calls to fuzzBounceDE() in various places can help.

Usually, one of the following serialization functions will let you replace everything above it:

* serializeHTML(), if the DOM tree isn't too weird to be serialized as HTML
* serializeXML(), if in standards mode (also change the extension to .xhtml)
* serializeDOMAsScript(), followed by another use of Lithium

Here's an example of a reduced testcase where exactly one modification was left dynamic:
view-source:https://bug366012.bugzilla.mozilla.org/attachment.cgi?id=250556


## Reducing non-layout testcases

* Replace variables with their values


## File the bug

When you've reduced the fuzzCommands array to a minimum, sweep the contents into a new function and call it from an onload handler.

Now that you have a simple testcase, you're ready to file a bug!  Use the "testcase" keyword and mark it as blocking the metabug for the module that found it.

If the fuzzer module is private, make sure the testcase is clean of hints about how the fuzzer works. Even if your bug is initially filed as a security-sensitive bug, it might become public before the fuzzer does.


## Appendix: tricky scenarios

### Unreliable testcases

If the testcase doesn't trigger the bug over 50% of the time, Lithium will reduce it slowly and manual reduction will be frustrating. You can often increase the reliability of a testcase with one of the following techniques:

* Make the testcase run the script several times. At the end of the fuzzCommands array, put `fun: fuzzReset(n)` to repeat the script or `fun: fuzzRetry(n)` to reload the entire page.
* Ensure the page doesn't depend on images or stylesheets that must be loaded from the Web.
* Fiddle with timers, or try replacing a timer with a listener for a relevant event.
* If you suspect the bug involves garbage-collection timing, add a manual call to `fuzzPriv.GC()` or `fuzzPriv.CC()`.
* If you suspect the bug involves memory corruption, try running under Address Sanitizer or Valgrind.
* If you suspect the bug involves uninitialized memory, try running under Memory Sanitizer or Valgrind.
* If you suspect the bug involves a data race, try running under Thread Sanitizer.

In the worst case, you can capture the bug under [rr](http://rr-project.org/) and work with a developer to debug the failure interactively.

### Long testcases

Sometimes, Lithium gives you something that has 20 or more lines.

For layout testcases, common culprits are wrapping bugs (where widths have to add up to some large amount in order to wrap) and -moz-column bugs (where the total height might be split into two equal parts, and the break point matters).  In both cases, you can use fuzzReset, and have one of the heights or widths depend on fuzzResetCount.  (Or you can just try forcing a small height or width to encourage maximal wrapping.)

For non-layout testcases, a slow or allocation-heavy testcase might trip Firefox's heuristics for running garbage collection. Adding a call to fuzzPriv.GC() or fuzzPriv.CC() near the bottom of the testcase might allow Lithium to remove most of the lines above it.


### Testcases with long lines

For text nodes, you can use `serializeDOMAsScript(null, true, true);` to split the text node into a bunch of `node.data += char` lines.

For stylesheets, you can often remove the document-emptying script, and move the stylesheet contents into markup as a `<style>` element:

```
<style>
/* DDBEGIN */
  ~~ lots of rules ~~
/* DDEND */
</style>
```

Otherwise, you can rearrange the testcase into a form that lets you run `lithium --char`:

```
<script>
// DDBEGIN
x = ' ~~ lots of text ~~ '
// DDEND
</script>
<script>
...
/* use x */
...
/* call fuzzPriv.quitApplication, even if Lithium introduced a syntax error into the first <script> */
...
</script>
```

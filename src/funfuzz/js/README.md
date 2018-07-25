## Compile SpiderMonkey using compile_shell

To compile a SpiderMonkey shell, run:

`<python executable> -m funfuzz.js.compile_shell -b "--enable-debug --enable-more-deterministic -R ~/trees/mozilla-central"`

in order to get a debug 64-bit deterministic shell, off the **Mercurial** repository located at `~/trees/mozilla-central`.

Clone the repository to that location using:

`hg clone https://hg.mozilla.org/mozilla-central/ ~/trees/mozilla-central`

assuming the `~/trees` folder is created and present.

## Additional information
* compile_shell
  * [More examples](examples.md)
  * [FAQ](faq.md)

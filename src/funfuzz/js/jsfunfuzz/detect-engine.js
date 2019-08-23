
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

/* exported gcIsQuiet, loopCount, loopModulo, readline, xpcshell */
/* global debug, gc, print, readline:writable, rnd, uneval:writable, verifyprebarriers, wasmIsSupported */
/* XPCNativeWrapper */

// jsfunfuzz is best run in a command-line shell.  It can also run in
// a web browser, but you might have trouble reproducing bugs that way.

var ENGINE_UNKNOWN = 0;
var ENGINE_SPIDERMONKEY_TRUNK = 1;
var ENGINE_JAVASCRIPTCORE = 4;

var engine = ENGINE_UNKNOWN;
var jsshell = (typeof window === "undefined"); /* eslint-disable-line no-undef */
var xpcshell = jsshell && (typeof Components === "object"); /* eslint-disable-line no-undef */
var dumpln;
var printImportant;

dumpln = print;
printImportant = function (s) { dumpln("***"); dumpln(s); };
if (typeof verifyprebarriers === "function") {
  // Run a diff between the help() outputs of different js shells.
  // Make sure the function to look out for is not located only in some
  // particular #ifdef, e.g. JS_GC_ZEAL, or controlled by --fuzzing-safe.
  if (typeof wasmIsSupported === "function") {
    engine = ENGINE_SPIDERMONKEY_TRUNK;
  }

  // Avoid accidentally waiting for user input that will never come.
  readline = function () {};
} else if (typeof XPCNativeWrapper === "function") { /* eslint-disable-line no-undef */
  // e.g. xpcshell or firefox
  engine = ENGINE_SPIDERMONKEY_TRUNK;
} else if (typeof debug === "function") {
  engine = ENGINE_JAVASCRIPTCORE;
}

// If WebAssembly object doesn't exist, make it an empty function, else runtime flags like --wasm-compiler=ion throw
if (typeof WebAssembly === "undefined") { this.WebAssembly = function () {}; }

if (typeof gc === "undefined") { this.gc = function () {}; }
var gcIsQuiet = !(gc()); // see bug 706433

// If the JavaScript engine being tested has heuristics like
//   "recompile any loop that is run more than X times"
// this should be set to the highest such X.
var HOTLOOP = 60;
function loopCount () { return rnd(rnd(HOTLOOP * 3)); } /* eslint-disable-line require-jsdoc */
function loopModulo () { return (rnd(2) ? rnd(rnd(HOTLOOP * 2)) : rnd(5)) + 2; } /* eslint-disable-line require-jsdoc */

function simpleSource (st) { /* eslint-disable-line require-jsdoc */
  function hexify (c) { /* eslint-disable-line require-jsdoc */
    var code = c.charCodeAt(0);
    var hex = code.toString(16);
    while (hex.length < 4) { hex = `0${hex}`; }
    return `\\u${hex}`;
  }

  if (typeof st === "string") {
    return ("\"" +
      st.replace(/\\/g, "\\\\")
        .replace(/"/g, "\\\"")
        .replace(/\0/g, "\\0")
        .replace(/\n/g, "\\n")
        .replace(/[^ -~]/g, hexify) + // not space (32) through tilde (126)
      "\"");
  } else { return `${st}`; } // hope this is right ;)  should work for numbers.
}

var haveRealUneval = (typeof uneval === "function");
if (!haveRealUneval) { uneval = simpleSource; }

if (engine === ENGINE_UNKNOWN) { printImportant("Targeting an unknown JavaScript engine!"); } else if (engine === ENGINE_SPIDERMONKEY_TRUNK) { printImportant("Targeting SpiderMonkey / Gecko (trunk)."); } else if (engine === ENGINE_JAVASCRIPTCORE) { printImportant("Targeting JavaScriptCore / WebKit."); }

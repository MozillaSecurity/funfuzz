
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

/* exported newFun, tryItOut */
/* global confused, count, dumpln, errorToString, failsToCompileInTry, gc, gczeal, jsStrictMode, optionalTests */
/* global resetOOMFailure, strTimes, tryRunning, uneval, verbose, whatToTest */

/* ******************* *
 * UNSANDBOXED RUNNING *
 * ******************* */

// Hack to make line numbers be consistent, to make spidermonkey
// disassemble() comparison testing easier (e.g. for round-trip testing)
function directEvalC (s) { var c; /* evil closureizer */ return eval(s); } /* eslint-disable-line no-eval,no-unused-vars,require-jsdoc */
function newFun (s) { return new Function(s); } /* eslint-disable-line no-new-func,require-jsdoc */

function tryRunningDirectly (f, code, wtt) { /* eslint-disable-line require-jsdoc */
  if (count % 23 === 3) {
    dumpln("Plain eval!");
    try { eval(code); } catch (e) { } /* eslint-disable-line no-eval */
    tryEnsureSanity();
    return;
  }

  if (count % 23 === 4) {
    dumpln("About to recompile, using eval hack.");
    f = directEvalC(`(function(){${code}});`);
  }

  try {
    if (verbose) { dumpln("About to run it!"); }
    f();
    if (verbose) { dumpln("It ran!"); }
  } catch (runError) {
    if (verbose) { dumpln("Running threw!  About to toString to error."); }
    var err = errorToString(runError);
    dumpln(`Running threw: ${err}`);
  }

  tryEnsureSanity();
}

// Store things now so we can restore sanity later.
var realEval = eval; /* eslint-disable-line no-eval */
var realMath = Math;
var realFunction = Function;
var realGC = gc;
var realUneval = uneval;
var realToString = toString;

function tryEnsureSanity () { /* eslint-disable-line require-jsdoc */
  // The script might have set up oomAfterAllocations or oomAtAllocation.
  // Turn it off so we can test only generated code with it.
  try {
    if (typeof resetOOMFailure === "function") { resetOOMFailure(); }
  } catch (e) { }

  try {
    // The script might have turned on gczeal.
    // Turn it off to avoid slowness.
    if (typeof gczeal === "function") { gczeal(0); }
  } catch (e) { }

  // At least one bug in the past has put exceptions in strange places.  This also catches "eval getter" issues.
  try { eval(""); } catch (e) { /* eslint-disable-line no-eval */
    dumpln(`That really shouldn't have thrown: ${errorToString(e)}`);
  }

  if (!this) {
    // Strict mode. Great.
    return;
  }

  try {
    if ("__defineSetter__" in this) {
      // The only way to get rid of getters/setters is to delete the property.
      if (!jsStrictMode) { delete this.eval; } /* eslint-disable-line no-eval */
      delete this.Math;
      delete this.Function;
      delete this.gc;
      delete this.uneval;
      delete this.toString;
    }

    this.Math = realMath;
    this.eval = realEval; /* eslint-disable-line no-eval */
    this.Function = realFunction;
    this.gc = realGC;
    this.uneval = realUneval;
    this.toString = realToString;
  } catch (e) {
    confused(`tryEnsureSanity failed: ${errorToString(e)}`);
  }

  // These can fail if the page creates a getter for "eval", for example.
  if (this.eval !== realEval) { confused("Fuzz script replaced |eval|"); } /* eslint-disable-line no-eval */
  if (Function !== realFunction) { confused("Fuzz script replaced |Function|"); }
}

function tryItOut (code) { /* eslint-disable-line require-jsdoc */
  // Accidentally leaving gczeal enabled for a long time would make jsfunfuzz really slow.
  if (typeof gczeal === "function") { gczeal(0); }

  // SpiderMonkey shell does not schedule GC on its own.  Help it not use too much memory.
  if (count % 1000 === 0) {
    dumpln(`Paranoid GC (count=${count})!`);
    realGC();
  }

  var wtt = whatToTest(code);

  if (!wtt.allowParse) { return; }

  code = code.replace(/\/\*DUPTRY\d+\*\//, function (k) { var n = parseInt(k.substr(8), 10); dumpln(n); return strTimes("try{}catch(e){}", n); });

  if (jsStrictMode) { code = `'use strict'; ${code}`; } // ES5 10.1.1: new Function does not inherit strict mode

  var f;
  try {
    f = new Function(code); /* eslint-disable-line no-new-func */
  } catch (compileError) {
    dumpln(`Compiling threw: ${errorToString(compileError)}`);
  }

  if (f && wtt.allowExec && wtt.expectConsistentOutput && wtt.expectConsistentOutputAcrossJITs) {
    if (code.indexOf("\n") === -1 && code.indexOf("\r") === -1 && code.indexOf("\f") === -1 && code.indexOf("\0") === -1 &&
        code.indexOf("\u2028") === -1 && code.indexOf("\u2029") === -1 &&
        code.indexOf("<--") === -1 && code.indexOf("-->") === -1 && code.indexOf("//") === -1) {
      // FCM cookie, lines with this cookie are used for compare_jit
      var cookie1 = "/*F";
      var cookie2 = "CM*/";
      var nCode = code;
      // Avoid compile-time errors because those are no fun.
      // But leave some things out of function(){} because some bugs are only detectable at top-level, and
      // pure jsfunfuzz doesn't test top-level at all.
      // (This is a good reason to use compare_jit even if I'm not interested in finding JIT bugs!)
      if (nCode.indexOf("return") !== -1 || nCode.indexOf("yield") !== -1 || nCode.indexOf("const") !== -1 || failsToCompileInTry(nCode)) { nCode = `(function(){${nCode}})()`; }
      dumpln(`${cookie1 + cookie2} try { ${nCode} } catch(e) { }`);
    }
  }

  if (tryRunning !== tryRunningDirectly) {
    optionalTests(f, code, wtt);
  }

  if (wtt.allowExec && f) {
    tryRunning(f, code, wtt);
  }

  if (verbose) { dumpln("Done trying out that function!"); }

  dumpln("");
}

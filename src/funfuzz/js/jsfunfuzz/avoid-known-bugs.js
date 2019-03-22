
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

/* exported whatToTest */
/* global engine, ENGINE_JAVASCRIPTCORE, ENGINE_SPIDERMONKEY_TRUNK, gcIsQuiet, jsshell */

/* eslint-disable complexity, no-multi-spaces */
function whatToTestSpidermonkeyTrunk (code) { /* eslint-disable-line require-jsdoc */
  // regexps can't match across lines, so replace whitespace with spaces.
  var codeL = code.replace(/\s/g, " ");

  return {

    allowParse: true,

    allowExec: unlikelyToHang(code)
      && (jsshell || code.indexOf("nogeckoex") === -1)
    ,

    // Ideally we'd detect whether the shell was compiled with --enable-more-deterministic
    // Ignore both within-process & across-process, e.g. nestTest mismatch & compare_jit
    expectConsistentOutput: true
       && (gcIsQuiet || code.indexOf("gc") === -1)
       && code.indexOf("/*NODIFF*/") === -1                // Ignore diff testing on these labels
       && code.indexOf(".script") === -1                   // Debugger; see bug 1237464
       && code.indexOf(".parameterNames") === -1           // Debugger; see bug 1237464
       && code.indexOf(".environment") === -1              // Debugger; see bug 1237464
       && code.indexOf(".onNewGlobalObject") === -1        // Debugger; see bug 1238246
       && code.indexOf(".takeCensus") === -1               // Debugger; see bug 1247863
       && code.indexOf(".findScripts") === -1              // Debugger; see bug 1250863
       && code.indexOf("Date") === -1                      // time marches on
       && code.indexOf("backtrace") === -1                 // shows memory addresses
       && code.indexOf("drainAllocationsLog") === -1       // drainAllocationsLog returns an object with a timestamp, see bug 1066313
       && code.indexOf("dumpObject") === -1                // shows heap addresses
       && code.indexOf("dumpHeap") === -1                  // shows heap addresses
       && code.indexOf("dumpStringRepresentation") === -1  // shows memory addresses
       && code.indexOf("evalInCooperativeThread") === -1   // causes diffs especially in --no-threads
       && code.indexOf("evalInWorker") === -1              // causes diffs in --no-threads vs --ion-offthread-compile=off
       && code.indexOf("getBacktrace") === -1              // getBacktrace returns memory addresses which differs depending on flags
       && code.indexOf("getLcovInfo") === -1
       && code.indexOf("load") === -1                      // load()ed regression test might output dates, etc
       && code.indexOf("offThreadCompileScript") === -1    // causes diffs in --no-threads vs --ion-offthread-compile=off
       && code.indexOf("oomAfterAllocations") === -1
       && code.indexOf("oomAtAllocation") === -1
       && code.indexOf("oomTest") === -1                   // causes diffs in --ion-eager vs --baseline-eager
       && code.indexOf("printProfilerEvents") === -1       // causes diffs in --ion-eager vs --baseline-eager
       && code.indexOf("promiseID") === -1                 // Promise IDs are for debugger-use only
       && code.indexOf("runOffThreadScript") === -1
       && code.indexOf("shortestPaths") === -1             // See bug 1308743
       && code.indexOf("inIon") === -1                     // may become true after several iterations, or return a string with --no-ion
       && code.indexOf("inJit") === -1                     // may become true after several iterations, or return a string with --no-baseline
       && code.indexOf("random") === -1
       && code.indexOf("timeout") === -1                   // time runs and crawls
    ,

    expectConsistentOutputAcrossIter: true
    // within-process, e.g. ignore the following items for nestTest mismatch
       && code.indexOf("options") === -1             // options() is per-cx, and the js shell doesn't create a new cx for each sandbox/compartment
    ,

    expectConsistentOutputAcrossJITs: true
    // across-process (e.g. running js shell with different run-time options) e.g. compare_jit
       && code.indexOf("isAsmJSCompilationAvailable") === -1  // Causes false positives with --no-asmjs
       && code.indexOf("'strict") === -1                      // see bug 743425
       && code.indexOf("disassemble") === -1                  // see bug 1237403 (related to asm.js)
       && code.indexOf("sourceIsLazy") === -1                 // see bug 1286407
       && code.indexOf("getAllocationMetadata") === -1        // see bug 1296243
       && code.indexOf(".length") === -1                      // bug 1027846
       /* eslint-disable no-control-regex */
       && !(codeL.match(/\/.*[\u0000\u0080-\uffff]/))       // doesn't stay valid utf-8 after going through python (?)
       /* eslint-enable no-control-regex */

  };
}
/* eslint-enable complexity, no-multi-spaces */

function whatToTestJavaScriptCore (code) { /* eslint-disable-line require-jsdoc */
  return {

    allowParse: true,
    allowExec: unlikelyToHang(code),
    expectConsistentOutput: false,
    expectConsistentOutputAcrossIter: false,
    expectConsistentOutputAcrossJITs: false

  };
}

function whatToTestGeneric (code) { /* eslint-disable-line require-jsdoc */
  return {
    allowParse: true,
    allowExec: unlikelyToHang(code),
    expectConsistentOutput: false,
    expectConsistentOutputAcrossIter: false,
    expectConsistentOutputAcrossJITs: false
  };
}

var whatToTest;
if (engine === ENGINE_SPIDERMONKEY_TRUNK) { whatToTest = whatToTestSpidermonkeyTrunk; } else if (engine === ENGINE_JAVASCRIPTCORE) { whatToTest = whatToTestJavaScriptCore; } else { whatToTest = whatToTestGeneric; }

function unlikelyToHang (code) { /* eslint-disable-line require-jsdoc */
  var codeL = code.replace(/\s/g, " ");

  // Things that are likely to hang in all JavaScript engines
  return true
    && code.indexOf("infloop") === -1
    && !(codeL.match(/for.*in.*uneval/)) // can be slow to loop through the huge string uneval(this), for example
    && !(codeL.match(/for.*for.*for/)) // nested for loops (including for..in, array comprehensions, etc) can take a while
    && !(codeL.match(/for.*for.*gc/))
  ;
}

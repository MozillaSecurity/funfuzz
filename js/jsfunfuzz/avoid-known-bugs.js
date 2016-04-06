function whatToTestSpidermonkeyTrunk(code)
{
  /* jshint laxcomma: true */
  // regexps can't match across lines, so replace whitespace with spaces.
  var codeL = code.replace(/\s/g, " ");

  return {

    allowParse: true,

    allowExec: unlikelyToHang(code)
      && (jsshell || code.indexOf("nogeckoex") == -1)
    ,

    allowIter: true,

    // Ideally we'd detect whether the shell was compiled with --enable-more-deterministic
    // Ignore both within-process & across-process, e.g. nestTest mismatch & compareJIT
    expectConsistentOutput: true
       && (gcIsQuiet || code.indexOf("gc") == -1)
       && code.indexOf("/*NODIFF*/") == -1                // Ignore diff testing on these labels
       && code.indexOf(".script") == -1                 // Debugger; see bug 1237464
       && code.indexOf(".parameterNames") == -1         // Debugger; see bug 1237464
       && code.indexOf(".environment") == -1            // Debugger; see bug 1237464
       && code.indexOf(".onNewGlobalObject") == -1      // Debugger; see bug 1238246
       && code.indexOf(".takeCensus") == -1             // Debugger; see bug 1247863
       && code.indexOf(".findScripts") == -1            // Debugger; see bug 1250863
       && code.indexOf("Date") == -1                      // time marches on
       && code.indexOf("backtrace") == -1                 // shows memory addresses
       && code.indexOf("drainAllocationsLog") == -1       // drainAllocationsLog returns an object with a timestamp, see bug 1066313
       && code.indexOf("dumpObject") == -1                // shows heap addresses
       && code.indexOf("dumpHeap") == -1                  // shows heap addresses
       && code.indexOf("dumpStringRepresentation") == -1  // shows memory addresses
       && code.indexOf("evalInWorker") == -1              // causes diffs in --no-threads vs --ion-offthread-compile=off
       && code.indexOf("getBacktrace") == -1              // getBacktrace returns memory addresses which differs depending on flags
       && code.indexOf("getLcovInfo") == -1
       && code.indexOf("load") == -1                      // load()ed regression test might output dates, etc
       && code.indexOf("offThreadCompileScript") == -1    // causes diffs in --no-threads vs --ion-offthread-compile=off
       && code.indexOf("oomAfterAllocations") == -1
       && code.indexOf("oomAtAllocation") == -1
       && code.indexOf("printProfilerEvents") == -1       // causes diffs in --ion-eager vs --baseline-eager
       && code.indexOf("validategc") == -1
       && code.indexOf("inIon") == -1                     // may become true after several iterations, or return a string with --no-ion
       && code.indexOf("inJit") == -1                     // may become true after several iterations, or return a string with --no-baseline
       && code.indexOf("random") == -1
       && code.indexOf("timeout") == -1                   // time runs and crawls
    ,

    expectConsistentOutputAcrossIter: true
    // within-process, e.g. ignore the following items for nestTest mismatch
       && code.indexOf("options") == -1             // options() is per-cx, and the js shell doesn't create a new cx for each sandbox/compartment
    ,

    expectConsistentOutputAcrossJITs: true
    // across-process (e.g. running js shell with different run-time options) e.g. compareJIT
       && code.indexOf("'strict") == -1                 // see bug 743425
       && code.indexOf("disassemble") == -1             // see bug 1237403 (related to asm.js)
       && code.indexOf("Number.MAX_VALUE") == -1        // bug 1246200
       && code.indexOf(".toString") == -1               // bug 1246552
       && code.indexOf("Array.prototype") == -1         // bug 1253898
       && !( codeL.match(/\/.*[\u0000\u0080-\uffff]/))  // doesn't stay valid utf-8 after going through python (?)

  };
}

function whatToTestSpidermonkeyMozilla31(code)
{
  /* jshint laxcomma: true */
  // regexps can't match across lines, so replace whitespace with spaces.
  var codeL = code.replace(/\s/g, " ");

  return {

    allowParse: true,

    allowExec: unlikelyToHang(code)
      && (jsshell || code.indexOf("nogeckoex") == -1)
    ,

    allowIter: true,

    // Ideally we'd detect whether the shell was compiled with --enable-more-deterministic
    expectConsistentOutput: true
       && (gcIsQuiet || code.indexOf("gc") == -1)
       && code.indexOf("Date") == -1                // time marches on
       && code.indexOf("random") == -1
       && code.indexOf("dumpObject") == -1          // shows heap addresses
       && code.indexOf("oomAfterAllocations") == -1
       && code.indexOf("reducePar") == -1           // only deterministic for associative elemental-reducers
       && code.indexOf("scanPar") == -1             // only deterministic for associative elemental-reducers
       && code.indexOf("scatterPar") == -1          // only deterministic for associative conflict-resolvers
    ,

    expectConsistentOutputAcrossIter: true
       && code.indexOf("options") == -1             // options() is per-cx, and the js shell doesn't create a new cx for each sandbox/compartment
    ,

    expectConsistentOutputAcrossJITs: true
       && code.indexOf("/*NODIFF*/") == -1          // Ignore diff testing on these labels
       && code.indexOf("'strict") == -1             // see bug 743425
       && code.indexOf("Object.seal") == -1         // bug 937922 (31 branch)
       && code.indexOf("length") == -1              // bug 998059 (31 branch)
       && code.indexOf("buildPar") == -1            // bug 998262 (31 branch)
       && code.indexOf("with") == -1                // bug 998580 (31 branch)
       && code.indexOf("use asm") == -1             // bug 999790 (31 branch)
       && code.indexOf("Math.round") == -1          // bug 1000606 (31 branch)
       && code.indexOf("Math.fround") == -1         // bug 1000606 (31 branch)
       && code.indexOf("Math.ceil") == -1           // bug 1000605 (31 branch)
       && code.indexOf("Math.asinh") == -1          // bug 1007213 (31 branch)
       && code.indexOf("use strict") == -1          // bug 1008818 (31 branch)
       && code.indexOf("Math.ceil") == -1           // bug 1015656 (31 branch)
       && code.indexOf("arguments") == -1           // bug 1024444 (31 branch)
       && code.indexOf("use strict") == -1          // bug 1025587 (31 branch)
       && code.indexOf("length") == -1              // bug 1027846 (31 branch)
       && code.indexOf("enumerable") == -1          // bug 1054545 (31 branch)
       && code.indexOf("buildPar") == -1            // bug 1066496 (31 branch)
       && !( codeL.match(/\/.*[\u0000\u0080-\uffff]/)) // doesn't stay valid utf-8 after going through python (?)

  };
}

function whatToTestJavaScriptCore(code)
{
  return {

    allowParse: true,
    allowExec: unlikelyToHang(code),
    allowIter: false, // JavaScriptCore does not support |yield| and |Iterator|
    expectConsistentOutput: false,
    expectConsistentOutputAcrossIter: false,
    expectConsistentOutputAcrossJITs: false

  };
}

function whatToTestGeneric(code)
{
  return {
    allowParse: true,
    allowExec: unlikelyToHang(code),
    allowIter: (typeof Iterator == "function"),
    expectConsistentOutput: false,
    expectConsistentOutputAcrossIter: false,
    expectConsistentOutputAcrossJITs: false
  };
}

var whatToTest;
if (engine == ENGINE_SPIDERMONKEY_TRUNK)
  whatToTest = whatToTestSpidermonkeyTrunk;
else if (engine == ENGINE_SPIDERMONKEY_MOZILLA31)
  whatToTest = whatToTestSpidermonkeyMozilla31;
else if (engine == ENGINE_JAVASCRIPTCORE)
  whatToTest = whatToTestJavaScriptCore;
else
  whatToTest = whatToTestGeneric;


function unlikelyToHang(code)
{
  var codeL = code.replace(/\s/g, " ");

  // Things that are likely to hang in all JavaScript engines
  return true
    && code.indexOf("infloop") == -1
    && !( codeL.match( /for.*in.*uneval/ )) // can be slow to loop through the huge string uneval(this), for example
    && !( codeL.match( /for.*for.*for/ )) // nested for loops (including for..in, array comprehensions, etc) can take a while
    && !( codeL.match( /for.*for.*gc/ ))
    ;
}

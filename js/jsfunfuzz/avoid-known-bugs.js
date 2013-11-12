function whatToTestSpidermonkeyTrunk(code)
{
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
       && code.indexOf("ParallelArray") == -1
    ,

    expectConsistentOutputAcrossIter: true
       && code.indexOf("options") == -1             // options() is per-cx, and the js shell doesn't create a new cx for each sandbox/compartment
    ,

    expectConsistentOutputAcrossJITs: true
       && code.indexOf("'strict") == -1             // see bug 743425
       && code.indexOf("__noSuchMethod__") == -1    // bug 912303
       && code.indexOf("gcPreserveCode") == -1      // bug 912328
       && !( codeL.match(/\/.*[\u0000\u0080-\uffff]/)) // doesn't stay valid utf-8 after going through python (?)

  };
}

function whatToTestSpidermonkeyMozilla17(code)
{
  // regexps can't match across lines, so replace whitespace with spaces.
  var codeL = code.replace(/\s/g, " ");

  return {

    allowParse: true,

    allowExec: unlikelyToHang(code)
      && code.indexOf("<>")       == -1 // avoid bug 334628 (17 branch), hopefully
      && (jsshell || code.indexOf("nogeckoex") == -1)
    ,

    allowIter: true,

    // Ideally we'd detect whether the shell was compiled with --enable-more-deterministic
    expectConsistentOutput: true
       && (gcIsQuiet || code.indexOf("gc") == -1)
       && code.indexOf("Date") == -1                // time marches on
       && code.indexOf("random") == -1
    ,

    expectConsistentOutputAcrossIter: true
       && code.indexOf("options") == -1             // options() is per-cx, and the js shell doesn't create a new cx for each sandbox/compartment
    ,

    expectConsistentOutputAcrossJITs: true
       && code.indexOf("getOwnPropertyNames") == -1 // Object.getOwnPropertyNames(this) contains "jitstats" and "tracemonkey", which exist only with -j
       && code.indexOf("lazy") == -1                // bug 743423 (17 branch), bug 743424 (17 branch)
       && code.indexOf("strict") == -1              // see bug 743425 (17 branch)
       && code.indexOf("QName") == -1              // See bug 748568 (17 branch)
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
else if (engine == ENGINE_SPIDERMONKEY_MOZILLA17)
  whatToTest = whatToTestSpidermonkeyMozilla17;
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
    && !( codeL.match( /const.*for/ )) // can be an infinite loop: function() { const x = 1; for each(x in ({a1:1})) dumpln(3); }
    && !( codeL.match( /for.*const/ )) // can be an infinite loop: for each(x in ...); const x;
    && !( codeL.match( /for.*in.*uneval/ )) // can be slow to loop through the huge string uneval(this), for example
    && !( codeL.match( /for.*for.*for/ )) // nested for loops (including for..in, array comprehensions, etc) can take a while
    && !( codeL.match( /for.*for.*gc/ ))
    ;
}

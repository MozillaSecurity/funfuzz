// Generate calls to SpiderMonkey "testing functions" for:
// * testing that they do not cause assertions/crashes
// * testing that they do not alter visible results (compareJIT with and without the call)

var fuzzTestingFunctions = (function(glob){

  var browser = "window" in glob;
  var prefix = browser ? "fuzzPriv." : "";

  function tf(funName) {
    if (!browser && (rnd(5) == 0)) {
      // Differential testing hack!
      // Take advantage of the fact that --no-asmjs flips isAsmJSCompilationAvailable().
      // (I couldn't find a better way to communicate from compareJIT to jsfunfuzz:
      // doing --execute='gcslice=function(){}' changes the result of uneval(this)!)
      var cond = (rnd(2) ? "!" : "") + "isAsmJSCompilationAvailable()";
      return "(" + cond + " ? " + funName + " : (function(){}))";
    }
    return prefix + funName;
  }

  function numberOfAllocs() { return Math.floor(Math.exp(rnd(rnd(6000)) / 1000)); }

  function global(d, b) { return ensureOneArg(browser ? Things.instance("Window") : makeExpr(d - 1, b)); }
  function object(d, b) { return ensureOneArg(browser ? Things.any() : makeExpr(d - 1, b)); }

  // Ensure that even if makeExpr returns "" or "1, 2", we only pass one argument to functions like schedulegc
  function ensureOneArg(s) { return "(null || (" + s + "))"; }

  function enableGCZeal()
  {
    var level = rnd(15);
    if (browser && level == 9) level = 0; // bug 815241
    var period = numberOfAllocs();
    return "(" + tf("gczeal") + "(" + level + ", " + period + ")" + ")";
  }

  function setGcparam() {
    switch(rnd(4)) {
      case 0:  return _set("sliceTimeBudget", rnd(100));
      case 1:  return _set("markStackLimit", rnd(2) ? (1 + rnd(30)) : 4294967295); // Artificially trigger delayed marking
      case 2:  return _set("maxBytes", _get("gcBytes") + " + " + (rnd(2) ? rnd(2) : rnd(4097))); // Make a near-future allocation fail
      default: return _set("maxBytes", 4294967295); // Restore the unlimited-ish default
    }

    function _set(name, value) {
      // try..catch because gcparam sets may throw, depending on GC state (see bug 973571)
      return "try { " + tf("gcparam") + "('" + name + "', " + value + ");" + " } catch(e) { }";
    }

    function _get(name) {
      return prefix + "gcparam" + "('" + name + "')";
    }
  }

  // Functions shared between the SpiderMonkey shell and Firefox browser
  // https://mxr.mozilla.org/mozilla-central/source/js/src/builtin/TestingFunctions.cpp
  var sharedTestingFunctions = [
    // Force garbage collection (global or specific compartment)
    { w: 10, v: function(d, b) { return "(void " + tf("gc") + "()" + ")"; } },
    { w: 10, v: function(d, b) { return "(void " + tf("gc") + "('compartment')" + ")"; } },
    { w: 5,  v: function(d, b) { return "(void " + tf("gc") + "(" + global(d, b) + ")" + ")"; } },

    // Run a minor garbage collection on the nursery.
    { w: 20, v: function(d, b) { return "(" + tf("minorgc") + "(false)" + ")"; } },
    { w: 20, v: function(d, b) { return "(" + tf("minorgc") + "(true)" + ")"; } },

    // Invoke an incremental garbage collection slice.
    { w: 20, v: function(d, b) { return "(" + tf("gcslice") + "(" + Math.floor(Math.pow(2, Random.float() * 32)) + ")" + ")"; } },

    // Schedule the given objects to be marked in the next GC slice.
    { w: 10, v: function(d, b) { return "(" + tf("selectforgc") + "(" + object(d, b) + ")" + ")"; } },

    // Add a compartment to the next garbage collection.
    { w: 10, v: function(d, b) { return "(" + tf("schedulegc") + "(" + global(d, b) + ")" + ")"; } },

    // Schedule a GC for after N allocations.
    { w: 10, v: function(d, b) { return "(" + tf("schedulegc") + "(" + numberOfAllocs() + ")" + ")"; } },

    // Change a GC parameter.
    { w: 10, v: setGcparam },

    // Make garbage collection extremely frequent (SLOW)
    { w: 1,  v: function(d, b) { return (!browser || rnd(100) == 0) ? (enableGCZeal()) : "0"; } },

    // Verify write barriers. These functions are effective in pairs.
    // The first call sets up the start barrier, the second call sets up the end barrier.
    // Nothing happens when there is only one call.
    { w: 10, v: function(d, b) { return "(" + tf("verifyprebarriers") + "()" + ")"; } },
    { w: 10, v: function(d, b) { return "(" + tf("verifypostbarriers") + "()" + ")"; } },

    // Trace the heap using non-GC tracing code
    { w: 1,  v: function(d, b) { return "(void " + tf("countHeap") + "()" + ")"; } },

    // Toggle various validations.
    { w: 5,  v: function(d, b) { return "(" + tf("validategc") + "(false)" + ")"; } },
    { w: 1,  v: function(d, b) { return "(" + tf("validategc") + "(true)" + ")"; } },
    { w: 5,  v: function(d, b) { return "(" + tf("fullcompartmentchecks") + "(false)" + ")"; } },
    { w: 1,  v: function(d, b) { return "(" + tf("fullcompartmentchecks") + "(true)" + ")"; } },
    { w: 5,  v: function(d, b) { return "(" + tf("setIonCheckGraphCoherency") + "(false)" + ")"; } },
    { w: 1,  v: function(d, b) { return "(" + tf("setIonCheckGraphCoherency") + "(true)" + ")"; } },
    { w: 1,  v: function(d, b) { return "(" + tf("enableOsiPointRegisterChecks") + "()" + ")"; } },

    // Run-time equivalents to --baseline-eager or --baseline-uses-before-compile, --no-baseline, etc
    { w: 1,  v: function(d, b) { return "(" + tf("setJitCompilerOption") + "('baseline.warmup.trigger', " + rnd(20) + ")" + ")"; } },
    { w: 1,  v: function(d, b) { return "(" + tf("setJitCompilerOption") + "('ion.warmup.trigger', " + rnd(40) + ")" + ")"; } },
    //{ w: 1,  v: function(d, b) { return tf("setJitCompilerOption") + "('ion.enable', " + rnd(2) + ")"; } }, // see bug 949807
    //{ w: 1,  v: function(d, b) { return tf("setJitCompilerOption") + "('baseline.enable', " + rnd(2) + ")"; } }, // bug 932284

    // Toggle the built-in profiler.
    { w: 1,  v: function(d, b) { return "(" + tf("enableSPSProfiling") + "()" + ")"; } },
    { w: 1,  v: function(d, b) { return "(" + tf("enableSPSProfilingWithSlowAssertions") + "()" + ")"; } },
    { w: 5,  v: function(d, b) { return "(" + tf("disableSPSProfiling") + "()" + ")"; } },

    // I'm not sure what this does in the shell.
    { w: 5,  v: function(d, b) { return "(" + tf("deterministicgc") + "(false)" + ")"; } },
    { w: 1,  v: function(d, b) { return "(" + tf("deterministicgc") + "(true)" + ")"; } },

    // Causes JIT code to always be preserved by GCs afterwards (see https://bugzilla.mozilla.org/show_bug.cgi?id=750834)
    { w: 5,  v: function(d, b) { return "(" + tf("gcPreserveCode") + "()" + ")"; } },
  ];

  // Functions only in the SpiderMonkey shell
  // https://mxr.mozilla.org/mozilla-central/source/js/src/shell/js.cpp
  var shellOnlyTestingFunctions = [
    // JIT bailout
    { w: 5,  v: function(d, b) { return "(" + tf("bailout") + "()" + ")"; } },

    // ARM simulator settings
    { w: 1,  v: function(d, b) { return "(void" + tf("disableSingleStepProfiling") + "()" + ")"; } },
    { w: 1,  v: function(d, b) { return "(" + tf("enableSingleStepProfiling") + "()" + ")"; } },

    // Force garbage collection with function relazification
    { w: 10, v: function(d, b) { return "(void " + tf("relazify") + "()" + ")"; } },
    { w: 10, v: function(d, b) { return "(void " + tf("relazify") + "('compartment')" + ")"; } },
    { w: 5,  v: function(d, b) { return "(void " + tf("relazify") + "(" + global(d, b) + ")" + ")"; } },
  ];

  var testingFunctions = Random.weighted(browser ? sharedTestingFunctions : sharedTestingFunctions.concat(shellOnlyTestingFunctions));

  return { testingFunctions: testingFunctions, enableGCZeal: enableGCZeal };

})(this);

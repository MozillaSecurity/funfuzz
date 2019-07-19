
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

/* exported fuzzTestingFunctionsCtor */
/* global finalLevel:writable, makeFunction, makeId, maxLevel:writable, oomAfterAllocations, oomAtAllocation */
/* global Random, resetOOMFailure, rnd */

// Generate calls to SpiderMonkey "testing functions" for:
// * testing that they do not cause assertions/crashes
// * testing that they do not alter visible results (compare_jit with and without the call)

function fuzzTestingFunctionsCtor (fGlobal) { /* eslint-disable-line require-jsdoc */
  function numberOfInstructions () { return Math.floor(Random.ludOneTo(10000)); } /* eslint-disable-line require-jsdoc */
  function numberOfAllocs () { return Math.floor(Random.ludOneTo(500)); } /* eslint-disable-line require-jsdoc */
  function gcSliceSize () { return Math.floor(Random.ludOneTo(0x100000000)); } /* eslint-disable-line require-jsdoc */
  function maybeCommaShrinking () { return rnd(5) ? "" : ", 'shrinking'"; } /* eslint-disable-line require-jsdoc */

  function enableGCZeal () { /* eslint-disable-line require-jsdoc */
    // As of m-c 451466:79cf24341024 2018-12-19
    // https://hg.mozilla.org/mozilla-central/file/79cf24341024/js/src/gc/GC.cpp#l1000
    maxLevel = 25;
    maxLevel++; // rnd function starts from zero
    var level = finalLevel = rnd(maxLevel - 3); // 3 levels disabled below

    // Generate the second level.
    // ref https://hg.mozilla.org/mozilla-central/file/02aa9c921aed/js/src/gc/GC.cpp#l1001
    var levelTwo = rnd(maxLevel - 3); // 3 levels disabled below
    if (levelTwo >= 3) ++levelTwo; // gczeal 3 does not exist, so repurpose it
    if (levelTwo >= 5) ++levelTwo; // gczeal 5 does not exist, so repurpose it
    if (levelTwo >= 6) ++levelTwo; // gczeal 6 does not exist, so repurpose it

    if (level >= 3) finalLevel = `"${++level};${levelTwo}"`; // gczeal 3 does not exist, so repurpose it
    if (level >= 5) finalLevel = `"${++level};${levelTwo}"`; // gczeal 5 does not exist, so repurpose it
    if (level >= 6) finalLevel = `"${++level};${levelTwo}"`; // gczeal 6 does not exist, so repurpose it

    var period = numberOfAllocs();
    return `gczeal(${finalLevel}, ${period});`;
  }

  function callSetGCCallback () { /* eslint-disable-line require-jsdoc */
    // https://dxr.mozilla.org/mozilla-central/source/js/src/shell/js.cpp - SetGCCallback
    var phases = Random.index(["both", "begin", "end"]);
    var actionAndOptions = rnd(2) ? `action: "majorGC", depth: ${rnd(17)}` : 'action: "minorGC"';
    var arg = `{ ${actionAndOptions}, phases: "${phases}" }`;
    return `setGCCallback(${arg});`;
  }

  function tryCatch (statement) { /* eslint-disable-line require-jsdoc */
    return `try { ${statement} } catch(e) { }`;
  }

  function setGcparam () { /* eslint-disable-line require-jsdoc */
    // Some switches from the following, added on 2019-05-07:
    // https://hg.mozilla.org/mozilla-central/file/3c70f36ad62c9c714db319/js/src/builtin/TestingFunctions.cpp#l478
    switch (rnd(12)) {
      /* eslint-disable no-multi-spaces */
      case 0:  return _set("sliceTimeBudgetMS", rnd(100));
      case 1:  return _set("minNurseryBytes", rnd(2) ? 0 : (1 + rnd(30))); // See bug 1540670
      case 2:  return _set("maxNurseryBytes", rnd(2) ? rnd(30) : (2 ** 32 - 1)); // See bug 1538594
      case 3:  return _set("mode", rnd(4));
      case 4:  return _set("dynamicHeapGrowth", rnd(2));
      case 5:  return _set("dynamicMarkSlice", rnd(2));
      case 6:  return _set("compactingEnabled", rnd(2));
      case 7:  return _set("minLastDitchGCPeriod", rnd(30));
      case 8:  return _set("maxEmptyChunkCount", rnd(40));
      case 9:  return _set("nurseryFreeThresholdForIdleCollectionPercent", (rnd(100) + 1));
      case 10: return _set("pretenureThreshold", (rnd(100) + 1));
      default: return _set("markStackLimit", rnd(2) ? (1 + rnd(30)) : 4294967295); // Artificially trigger delayed marking
      /* eslint-enable no-multi-spaces */
    }

    function _set (name, value) { /* eslint-disable-line require-jsdoc */
      // try..catch because gcparam sets may throw, depending on GC state (see bug 973571)
      return tryCatch(`gcparam('${name}', ${value});`);
    }
  }

  // https://mxr.mozilla.org/mozilla-central/source/js/src/builtin/TestingFunctions.cpp
  var sharedTestingFunctions = [
    /* eslint-disable no-multi-spaces */
    // Force garbage collection (global or specific compartment)
    { w: 10, v: function (d, b) { return `void gc();`; } },
    { w: 10, v: function (d, b) { return `void gc('compartment'${maybeCommaShrinking()});`; } },
    { w: 5,  v: function (d, b) { return `void gc(${fGlobal(d, b)}${maybeCommaShrinking()});`; } },
    /* eslint-enable no-multi-spaces */

    // Run a minor garbage collection on the nursery.
    { w: 20, v: function (d, b) { return `minorgc(false);`; } },
    { w: 20, v: function (d, b) { return `minorgc(true);`; } },

    // Start, continue, or abort incremental garbage collection.
    // startgc can throw: "Incremental GC already in progress"
    { w: 20, v: function (d, b) { return tryCatch(`startgc(${gcSliceSize()}${maybeCommaShrinking()});`); } },
    { w: 20, v: function (d, b) { return `gcslice(${gcSliceSize()});`; } },
    { w: 10, v: function (d, b) { return `abortgc();`; } },

    // Schedule the given objects to be marked in the next GC slice.
    { w: 10, v: function (d, b) { return `selectforgc(${fGlobal(d, b)});`; } },

    // Add a compartment to the next garbage collection.
    { w: 10, v: function (d, b) { return `void schedulegc(${fGlobal(d, b)});`; } },

    // Schedule a GC for after N allocations.
    { w: 10, v: function (d, b) { return `void schedulegc(${numberOfAllocs()});`; } },

    // Change a GC parameter.
    { w: 10, v: setGcparam },

    // Verify write barriers. This functions is effective in pairs.
    // The first call sets up the start barrier, the second call sets up the end barrier.
    // Nothing happens when there is only one call.
    { w: 10, v: function (d, b) { return `verifyprebarriers();`; } },

    // hasChild(parent, child): Return true if |child| is a child of |parent|, as determined by a call to TraceChildren.
    // We ignore the return value because hasChild can be used to see which WeakMap entries have been GCed.
    { w: 1, v: function (d, b) { return `void hasChild(${fGlobal(d, b)}, ${fGlobal(d, b)});`; } },

    // Various validation functions (toggles)
    { w: 5, v: function (d, b) { return `fullcompartmentchecks(false);`; } },
    { w: 1, v: function (d, b) { return `fullcompartmentchecks(true);`; } },
    { w: 5, v: function (d, b) { return `setIonCheckGraphCoherency(false);`; } },
    { w: 1, v: function (d, b) { return `setIonCheckGraphCoherency(true);`; } },
    { w: 1, v: function (d, b) { return `enableOsiPointRegisterChecks();`; } },

    // Various validation functions (immediate)
    { w: 1, v: function (d, b) { return `assertJitStackInvariants();`; } },

    // Run-time equivalents to --baseline-eager, --baseline-warmup-threshold, --ion-eager, --ion-warmup-threshold
    { w: 1, v: function (d, b) { return `setJitCompilerOption('baseline.warmup.trigger', ${rnd(20)});`; } },
    { w: 1, v: function (d, b) { return `setJitCompilerOption('ion.warmup.trigger', ${rnd(40)});`; } },

    // Test the baseline compiler
    { w: 10, v: function (d, b) { return `baselineCompile();`; } },

    // Force inline cache.
    { w: 1, v: function (d, b) { return `setJitCompilerOption('ion.forceinlineCaches', ${rnd(2)});`; } },

    // Run-time equivalents to --no-ion, --no-baseline
    // These can throw: "Can't turn off JITs with JIT code on the stack."
    { w: 1, v: function (d, b) { return tryCatch(`setJitCompilerOption('ion.enable', ${rnd(2)});`); } },
    { w: 1, v: function (d, b) { return tryCatch(`setJitCompilerOption('baseline.enable', ${rnd(2)});`); } },

    // Test the built-in profiler.
    { w: 1, v: function (d, b) { return `enableGeckoProfiling();`; } },
    { w: 1, v: function (d, b) { return `enableGeckoProfilingWithSlowAssertions();`; } },
    { w: 5, v: function (d, b) { return `disableGeckoProfiling();`; } },
    { w: 1, v: function (d, b) { return `void readGeckoProfilingStack();`; } },

    // I'm not sure what this does in the shell.
    { w: 5, v: function (d, b) { return `deterministicgc(false);`; } },
    { w: 1, v: function (d, b) { return `deterministicgc(true);`; } },

    // Causes JIT code to always be preserved by GCs afterwards (see https://bugzilla.mozilla.org/show_bug.cgi?id=750834)
    { w: 5, v: function (d, b) { return `gcPreserveCode();`; } },

    // Generate an LCOV trace (but throw away the returned string)
    { w: 1, v: function (d, b) { return `void getLcovInfo();`; } },
    { w: 1, v: function (d, b) { return `void getLcovInfo(${fGlobal(d, b)});`; } },

    // JIT bailout
    { w: 5, v: function (d, b) { return `bailout();`; } },
    { w: 10, v: function (d, b) { return `bailAfter(${numberOfInstructions()});`; } },

    // Enable some slow Shape assertions. See bug 1412289
    { w: 1, v: function (d, b) { return `enableShapeConsistencyChecks();`; } },

    // Create gray root Array for the current compartment. See bug 1452602
    { w: 1, v: function (d, b) { return `grayRoot();`; } },

    // Test monitorType as per bug 1560070
    { w: 10, v: function (d, b) { return `monitorType(${(rnd(2) ? makeFunction(d, b) : undefined)}, ${rnd(1000)}, ${(rnd(2) ? (rnd(2) ? "unknown" : "unknownObject") : makeId(d, b))});`; } }
  ];

  // Functions only in the SpiderMonkey shell
  // https://mxr.mozilla.org/mozilla-central/source/js/src/shell/js.cpp
  var shellOnlyTestingFunctions = [
    // ARM simulator settings
    // These throw when not in the ARM simulator.
    { w: 1, v: function (d, b) { return tryCatch(`(voiddisableSingleStepProfiling())`); } },
    { w: 1, v: function (d, b) { return tryCatch(`(enableSingleStepProfiling())`); } },

    // Force garbage collection with function relazification
    { w: 10, v: function (d, b) { return `void relazifyFunctions();`; } },
    { w: 10, v: function (d, b) { return `void relazifyFunctions('compartment');`; } },
    { w: 5, v: function (d, b) { return `void relazifyFunctions(${fGlobal(d, b)});`; } },

    // Test recomputeWrappers - see bug 1492406
    { w: 10, v: function (d, b) { return `recomputeWrappers();`; } },
    // Also test recomputeWrappers calling newGlobal, see the bug

    // [TestingFunctions.cpp, but debug-only and CRASHY]
    // After N js_malloc memory allocations, fail every following allocation
    { w: 1, v: function (d, b) { return (typeof oomAfterAllocations === "function" && rnd(1000) === 0) ? `oomAfterAllocations(${numberOfAllocs() - 1});` : "void 0;"; } },
    // After N js_malloc memory allocations, fail one allocation
    { w: 1, v: function (d, b) { return (typeof oomAtAllocation === "function" && rnd(100) === 0) ? `oomAtAllocation(${numberOfAllocs() - 1});` : "void 0;"; } },
    // Reset either of the above
    { w: 1, v: function (d, b) { return (typeof resetOOMFailure === "function") ? `void resetOOMFailure();` : "void 0;"; } },

    // [TestingFunctions.cpp, but SLOW]
    // Make garbage collection extremely frequent
    { w: 1, v: function (d, b) { return (rnd(100) === 0) ? (enableGCZeal()) : "void 0;"; } },

    { w: 10, v: callSetGCCallback }
  ];

  var testingFunctions = Random.weighted(sharedTestingFunctions.concat(shellOnlyTestingFunctions));

  return { testingFunctions: testingFunctions, enableGCZeal: enableGCZeal };
}

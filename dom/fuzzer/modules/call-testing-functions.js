var fuzzerTestingFunctions = (function() {

  function bool() { return rnd(2) ? "true" : "false"; }

  var browserTestingFunctions = Random.weighted([
    { w: 5, v: function() { return "fuzzPriv.CC(" + (rnd(7)-1) + ");"; } }, // the argument is aExtraForgetSkippableCalls
    { w: 5, v: function() { return "fuzzPriv.MP();"; } },
    { w: 5, v: function() { return "fuzzPriv.forceShrinkingGC();"; } },
    { w: 5, v: function() { return "fuzzPriv.forceGC();"; } }, // force GC with reason |js::gcreason::COMPONENT_UTILS|
    { w: 5, v: function() { return "fuzzPriv.schedulePreciseShrinkingGC();"; } },
    { w: 5, v: function() { return "fuzzPriv.schedulePreciseGC();"; } },
    { w: 1, v: function() { return "fuzzPriv.CCLog(" + bool() + ", " + bool() + ", " + (rnd(7)-1) + ");"; } },
  ]);

  function makeCommand()
  {
    if (rnd(30)) {
      return [];
    }

    if (rnd(100) === 0) {
      return fuzzTestingFunctions.enableGCZeal() + "; try { " + fuzzSubCommand() + " } finally { fuzzPriv.gczeal(0); }";
    }

    if (rnd(3) === 0) {
      return Random.index(browserTestingFunctions)();
    }

    return Random.index(fuzzTestingFunctions.testingFunctions)() + ";";
  }

  return { makeCommand: makeCommand };
})();

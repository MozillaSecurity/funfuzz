var fuzzerAccessibility = (function() {
  function makeCommand()
  {
    if (rnd(100) === 0)
      return "fuzzPriv.enableAccessibility();";
    return [];
  }
  return { makeCommand: makeCommand };
})();

registerModule("fuzzerAccessibility", 5);

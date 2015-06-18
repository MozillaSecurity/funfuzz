var fuzzerRepeat = (function() {
  function makeCommand()
  {
    // Avoid infinite recursion if we're alone
    if (rnd(2) === 0)
      return [];

    var sc = fuzzSubCommand();

    // Avoid nested loops, which are slow and make us think about how to scope the loop index.
    if (sc.indexOf("fuzzRepeat") != -1)
      return [];

    var loops = (rnd(5) + 1) * (rnd(5) + 1) * (rnd(5) + 1) * (rnd(5) + 1);

    return "for (var fuzzRepeat = 0; fuzzRepeat < " + loops + "; ++fuzzRepeat) { " + sc + " }";
  }

  return {
    makeCommand: makeCommand,
  };
})();

registerModule("fuzzerRepeat", 1);

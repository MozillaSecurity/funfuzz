var fuzzerMozSetImageElement = (function() {
  function makeCommand()
  {
    var nameToOverride = Random.pick(fuzzValues.names);
    var elementToUse = rnd(2) ? Things.instance("Element") : "null";
    return "document.mozSetImageElement(" + simpleSource(nameToOverride) + ", " + elementToUse + ");";
  }
  return { makeCommand: makeCommand };
})();

registerModule("fuzzerMozSetImageElement", 1);

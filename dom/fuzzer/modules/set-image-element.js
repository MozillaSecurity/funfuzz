var fuzzerMozSetImageElement = (function() {
  function makeCommand()
  {
    var nameToOverride = randomThing(fuzzValues.names);
    var elementToUse = rnd(2) ? (pick("nodes")) : "null";
    return "document.mozSetImageElement(" + simpleSource(nameToOverride) + ", " + elementToUse + ");";
  }
  return { makeCommand: makeCommand };
})();

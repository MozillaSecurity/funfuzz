

var fuzzerDocumentFragments = (function(){
  function makeCommand()
  {
    var newFrag = Things.reserve();
    switch(rnd(2)) {
    case 0:
      return newFrag + " = document.createDocumentFragment();";
    default:
      return [
        newFrag + " = document.createDocumentFragment();",
        newFrag + ".write(" + simpleSource(Random.pick(fuzzValues.htmlMarkup)) + ");"
      ];
    }
  }
  return { makeCommand: makeCommand };
})();
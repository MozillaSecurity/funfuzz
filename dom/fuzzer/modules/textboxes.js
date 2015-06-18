var fuzzerTextboxes = (function() {
  var selDirections = ["forward", "backward", "none"];
  var textInputElements = ["input", "textarea"];
  var max = 100;

  function internallySelectable()
  {
    return rnd(2) ? Things.instance("HTMLInputElement") : Things.instance("HTMLTextAreaElement");
  }

  function makeCommand()
  {
    switch(rnd(10)) {
      case 0:  return internallySelectable() + ".selectionStart = " + rnd(max) + ";";
      case 1:  return internallySelectable() + ".selectionEnd = " + rnd(max) + ";";
      case 2:  return internallySelectable() + ".selectionDirection = " + simpleSource(Random.index(selDirections)) + ";";
      case 3:  return internallySelectable() + ".setSelectionRange(" + rnd(max) + ", " + rnd(max) + ", " + simpleSource(Random.index(selDirections)) + ");";
      case 4:  var newnode = Things.reserve(); return newnode + " = document.createElementNS(\"http://www.w3.org/1999/xhtml\", " + simpleSource(Random.index(textInputElements)) + "); document.documentElement.appendChild(" + newnode + ");";
      case 5:  return Things.instance("Node") + ".focus();";
      case 6:  return Things.instance("Node") + ".select();";
      case 7:  return Things.instance("Node") + ".blur();";
      default: return Things.instance("Element") + ".value = " + simpleSource(Random.pick(fuzzValues.texts)) + ";";
    }
  }

  return { makeCommand: makeCommand };
})();

registerModule("fuzzerTextboxes", 1);

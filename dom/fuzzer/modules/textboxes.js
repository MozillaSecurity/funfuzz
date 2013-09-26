var fuzzerTextboxes = (function() {
  var selDirections = ["forward", "backward", "none"];
  var textInputElements = ["input", "textarea"];
  var max = 100;

  function makeCommand()
  {
    switch(rnd(10)) {
      case 0:  return pick("nodes") + ".selectionStart = " + rnd(max) + ";";
      case 1:  return pick("nodes") + ".selectionEnd = " + rnd(max) + ";";
      case 2:  return pick("nodes") + ".selectionDirection = " + simpleSource(rndElt(selDirections)) + ";";
      case 3:  return pick("nodes") + ".setSelectionRange(" + rnd(max) + ", " + rnd(max) + ", " + simpleSource(rndElt(selDirections)) + ");";
      case 4:  var newnode = nextSlot("nodes"); return newnode + " = document.createElementNS(\"http://www.w3.org/1999/xhtml\", " + simpleSource(rndElt(textInputElements)) + "); document.documentElement.appendChild(" + newnode + ");";
      case 5:  return nextSlot("nodes") + ".focus();";
      case 6:  return nextSlot("nodes") + ".select();";
      case 7:  return nextSlot("nodes") + ".blur();";
      default: return pick("nodes") + ".value = " + simpleSource(randomThing(fuzzValues.texts)) + ";";
    }
  }

  return { makeCommand: makeCommand };
})();
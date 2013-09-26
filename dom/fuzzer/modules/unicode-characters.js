var fuzzerChars = (function() {

  var lastElementIndex = null;

  function slashU(c)
  {
    var cHex = c.toString(16).toUpperCase();
    while (cHex.length < 4)
      cHex = "0" + cHex;
    return "\\u" + cHex;
  }

  function randomQuotedString()
  {
    switch(rnd(15)) {
    case 0:
      return simpleSource(randomThing(fuzzValues.texts));
    default:
      return simpleSource(randomThing(fuzzValues.chars));
    }
  }

  function makeCommand()
  {
    // First, pick a random node.  If it's a text node, do something with it.
    var t1index = rnd(all.nodes.length);
    var t1 = all.nodes[t1index];
    if (t1 && typeof t1 == "object" && "nodeType" in t1 && t1.nodeType == 3) {
      var commandt1 = "all.nodes[" + t1index + "]";
      return makeTextNodeCommand(t1, commandt1);
    }

    // Otherwise, pick a (separate) *element* node, perhaps "caching",
    // and do something with it.
    if (lastElementIndex == null || rnd(30) === 0) {
      var newIndex = randomElementIndex();
      if (newIndex == null && lastElementIndex == null)
        return [];
      if (newIndex != null)
        lastElementIndex = newIndex;
    }

    return makeElementCommand(all.nodes[lastElementIndex], "all.nodes[" + lastElementIndex + "]");
  }

  function makeElementCommand(n1, commandn1)
  {
    // Sometimes, call normalize, which is evil.
    switch(rnd(500)) {
    case 0:
      return commandn1 + ".normalize();";
    case 1:
      return "document.normalize();";
    case 2:
      return "document.normalizeDocument();";
    }

    var c = "createTextNode";
    switch(rnd(100)) {
    case 0:
      c = "createComment";
      break;
    case 1:
      c = "createCDATASection";
      break;
    }

    // Append the new text-ish node to the element.
    var newb = nextSlot("nodes");
    return [
      newb + " = document." + c + "(" + randomQuotedString() + ");",
      commandn1 + ".appendChild(" + newb + ");"
    ];
  }

  function makeTextNodeCommand(n1, commandn1)
  {
    switch(rnd(6)) {
    case 0:
      // Remove it.
      return "rM(" + commandn1 + ");";
    case 1:
      // Replace its text.
      return commandn1 + ".data = " + randomQuotedString() + ";";
    case 2:
      // Remove a character from its text.
      if (n1.data.length == 0)
        return [];
      var ix = rnd(n1.data.length);
      return "var d = " + commandn1 + ".data; " +
             commandn1 + ".data = d.substr(0, " + ix + ") + d.slice(" + (ix+1) + ");";
    case 3:
      // Split the text node.
      var splitIndex = rnd(n1.data.length + 1);
      return nextSlot("nodes") + " = " + commandn1 + ".splitText(" + splitIndex + ");";
    case 4:
      // Prepend to its text.
      return commandn1 + ".data = " + randomQuotedString() + " + " + commandn1 + ".data;";
    default:
      // Append to its text.
      return commandn1 + ".data += " + randomQuotedString() + ";";
    }
  }

  // Earlier versions of the fuzzer did things like this:
  //    return "var e = " + commandn1 + "; e.textContent = e.textContent.slice(1);";
  //    return "var e = " + commandn1 + "; e.textContent = e.textContent.substr(0, e.textContent.length - 1);";

  // This had the disadvantage  of both:
  // * Normalizes and throws away all.nodes indices

  // Previous versions also did the same with .innerHTML, which was even worse
  // for reduction.


  // Disadvantages with runtime getters:
  // * Lithium gives you something that's 1-minimal rather than 2-minimal
  //     due to slice.
  // * Mysterious dependencies on random classes (the *text* of the CSS sneaks in)

  // Disadvantages with makeCommand-time getters:
  // * Can have a huge blob of text left over after "Lithium L", which
  //     then has to be reduced with "Lithium C".  (May include "text"
  //     from Random Classes.)



  return {
    makeCommand: makeCommand,
    randomQuotedString: randomQuotedString
  };
})();

var fuzzerInnerHTML = (function() {
  // XXX should generate XHTML when in (or targeting) an XML document, because HTML-style markup is rejected

  function makeCommand() {
    window.disableCrazyURIs = true; // prevent too much recursion. kludgy :(

    // this is boring in anything but HTML (including XHTML), because
    // most of the generated tag soup is not well-formed :(

    // Could additionally use ".innerHTML += ..." but that's messy.

    var commandn1 = Things.instance("Element");
    if (rnd(2)) {
      return commandn1 + "." + rndElt(["innerHTML", "outerHTML"]) + " = " + simpleSource(fuzzValues.generateHTML(rnd(15))) + ";";
    } else {
      var where = rndElt(["beforeBegin", "afterBegin", "beforeEnd", "afterEnd"]);
      return commandn1 + ".insertAdjacentHTML(" + simpleSource(where) + ", " + simpleSource(fuzzValues.generateHTML(rnd(10))) + ");";
    }
  }

  return { makeCommand: makeCommand };
})();
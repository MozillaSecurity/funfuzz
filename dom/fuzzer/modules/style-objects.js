var fuzzerDOMStyle = (function() {
  // This fuzzer deals with three slightly different types of objects:
  // (0) immutable "CSSStyleDeclaration" objects (returned by getComputedStyle)
  // (1) mutable "CSS2Properties" objects (node.style)
  // (2) mutable "CSSStyleDeclaration" objects (cssRule.style)
  // The relationship between these objects, which I don't fully understand, is described in
  // http://www.w3.org/TR/DOM-Level-2-Style/css.html#CSS-CSS2Properties

  function makeCommand()
  {
    switch(rnd(5)) {
      case 0:
        // Get a computed style object.
        var pseudoElt = rnd(4) ? "null" : simpleSource(randomThing(fuzzValues.cssPseudoElements));
        return nextSlot("CSSStyleDeclarations") + " = " + pick("windows") + "." + rndElt(["getComputedStyle", "getDefaultComputedStyle"]) + "(" + pick("nodes") + ", " + pseudoElt + ");";
      case 1:
        // Get a style object off a node.
        return nextSlot("CSSStyleDeclarations") + " = " + pick("nodes") + ".style;";
      case 2:
        // Get a style object off a cssRule.
        if (all.CSSRules.length) {
          return nextSlot("CSSStyleDeclarations") + " = " + pick("CSSRules") + ".style;";
        }
        return [];
      case 3:
        // Grab a property value.
        if (all.CSSStyleDeclarations.length) {
          return addIfNovel('strings', pick("CSSStyleDeclarations") + ".getPropertyValue(" + simpleSource(rndElt(fuzzerRandomClasses.CSSPropList)) + ")");
        }
        return [];
      default:
        // Grab a CSSPrimitiveValue object. (Only works for computed styles, and for non-shorthands)
        // Note: I'm not really sure what to do with the CSSPrimitiveValue object, so I'm letting fuzzerRandomJS have at it.
        if (all.CSSStyleDeclarations.length) {
          return addIfNovel('nodes', pick("CSSStyleDeclarations") + ".getPropertyCSSValue(" + simpleSource(rndElt(fuzzerRandomClasses.CSSPropList)) + ")");
        }
        return [];
    }
  }

  return { makeCommand: makeCommand };
})();


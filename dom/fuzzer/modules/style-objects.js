var fuzzerDOMStyle = (function() {

  // This fuzzer deals with three slightly different types of objects:
  // * immutable "CSSStyleDeclaration" objects (returned by getComputedStyle)
  // * mutable "CSSStyleDeclaration" objects (cssRule.style)
  // * mutable "CSS2Properties" objects (element.style), which are instanceof CSSStyleDeclaration
  //
  // The relationship between these objects, which I don't fully understand, is described in
  // http://www.w3.org/TR/DOM-Level-2-Style/css.html#CSS-CSS2Properties

  function makeCommand()
  {
    switch(rnd(5)) {
      case 0:
        // Get a computed style object from an element.
        var pseudoElt = rnd(4) ? "null" : simpleSource(Random.pick(fuzzValues.cssPseudoElements));
        var f = Random.index(["getComputedStyle", "getDefaultComputedStyle"]);
        return Things.add(Things.instance("Window") + "." + f + "(" + Things.instance("Element") + ", " + pseudoElt + ")");
      case 1:
        // Get a style object off an element.
        return Things.add(Things.instance("Element") + ".style");
      case 2:
        // Get a style object off a CSSStyleRule.
        return Things.add(Things.instance("CSSStyleRule") + ".style");
      case 3:
        // Grab a property value.
        return Things.add(Things.instance("CSSStyleDeclaration") + ".getPropertyValue(" + simpleSource(fuzzerRandomClasses.randomProperty()) + ")");
      default:
        // Grab a CSSPrimitiveValue object. (Only works for computed styles, and for non-shorthands)
        // Note: I'm not really sure what to do with the CSSPrimitiveValue object, so I'm letting fuzzerRandomJS have at it.
        return Things.add(Things.instance("CSSStyleDeclaration") + ".getPropertyCSSValue(" + simpleSource(fuzzerRandomClasses.randomProperty()) + ")");
    }
  }

  return { makeCommand: makeCommand };
})();

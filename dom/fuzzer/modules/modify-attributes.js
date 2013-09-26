var fuzzerModifyAttributes = (function() {

  var storedValue = "";

  function makeCommand()
  {
    var n1index = randomElementIndex();
    var n1 = all.nodes[n1index];
    var commandn1 = "all.nodes[" + n1index + "]";

    if (!n1 ||
        !n1.attributes ||
        !n1.attributes.length
        )
        return " /* fuzzerModifyAttributes: nothing to do here */";

    var attr = rndElt(n1.attributes);

    var oldValue = attr.value;
    var newValue = rnd(10) ? fuzzValues.modifyText(oldValue) : storedValue;
    storedValue = oldValue;

    return "/*fMA*/ " + commandn1 + ".setAttributeNS(" + simpleSource(attr.namespaceURI) + ", " + simpleSource(attr.name) + ", " + simpleSource(newValue) + ");";
  }

  return { makeCommand: makeCommand };
})();
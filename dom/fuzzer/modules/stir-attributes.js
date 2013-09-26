var fuzzerStirAttributes = (function() {

  function makeCommand()
  {
    var n1index = randomElementIndex();
    var n2index = randomElementIndex();

    var n1 = all.nodes[n1index];
    var n2 = all.nodes[n2index];

    if ( n1 == n2 ||
        !n1 ||
        !n2 ||
        !n1.attributes ||
        !n2.attributes ||
        !n1.attributes.length
        )
        return " /* stirattributes: nothing to do here */";

    // Pick an attribute 'attr' on n1, and swap n1.attr with n2.attr.
    // If n2 doesn't have this attr, that means calling removeAttribute on n1.
    // (Conservation of name-value pairs!)

    var commandn1 = "all.nodes[" + n1index + "]";
    var commandn2 = "all.nodes[" + n2index + "]";

    var attr = rndElt(n1.attributes);

    var c1, c2, n2has, n2val;

    // Note that hasAttributeNS, getAttributeNS, and removeAttributeNS want a local name (.localName),
    // but setAttributeNS wants a qualified name (.name).

    try {
      var n2has = typeof n2.hasAttributeNS == "function" && !!n2.hasAttributeNS(attr.namespaceURI, attr.localName);
      if (n2has) {
        n2val = "" + n2.getAttributeNS(attr.namespaceURI, attr.localName);
      }
    } catch(e) {
      dumpln("fsa: " + e);
      return [];
    }

    addImmIfNovel(all.strings, attr.value);
    addImmIfNovel(all.strings, attr.name);

    if (n2has)
      c1 = commandn1 + ".setAttributeNS(" + simpleSource(attr.namespaceURI) + ", " + simpleSource(attr.name) + ", " + simpleSource(n2val) + ");";
    else
      c1 = commandn1 + ".removeAttributeNS(" + simpleSource(attr.namespaceURI) + ", " + simpleSource(attr.localName) + ");";

    c2 = commandn2 + ".setAttributeNS(" + simpleSource(attr.namespaceURI) + ", " + simpleSource(attr.name) + ", " + simpleSource(attr.value) + ");";

    return [c1, c2];
  }

  return { makeCommand: makeCommand };
})();
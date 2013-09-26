var fuzzerCloneNode = (function() {
  function makeCommand() {
    var n1index = randomElementIndex();
    if (n1index == null)
      return [];
    var commandn1 = "all.nodes[" + n1index + "]";

    var n2index = rnd(all.nodes.length);
    var commandn2 = "all.nodes[" + n2index + "]";
    var n2 = all.nodes[n2index];

    var deep = rndElt(["true", "false"]);

    try {
      if (n2.getElementsByTagName("*").length > 20) {
        deep = "false";
      }
    } catch(e) {
      return [];
    }

    var newb = nextSlot("nodes");

    return [
      newb + " = " + commandn2 + ".cloneNode(" + deep + ");",
      commandn1 + ".appendChild(" + newb + ");"
    ];
  }

  return { makeCommand: makeCommand };
})();
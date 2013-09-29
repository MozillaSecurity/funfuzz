

var fuzzerStirDOM = (function() {

  function makeCommand()
  {
    var n1index = Things.instanceIndex("Node");
    var n2index = Things.instanceIndex("Node");

    var n1 = o[n1index];
    var n2 = o[n2index];

    var commandn1 = "o[" + n1index + "]";
    var commandn2 = "o[" + n2index + "]";

    if (n2 == document.documentElement || n2 == document.body)
      return []; // removing the root is reserved for a separate routine

    // Move n2 in some way, with a new location based on the location of n1.

    if (rnd(120) === 1) {
      // Infrequently, remove nodes from the document tree.
      return "rM(" + commandn2 + ");";
    }

    if (rnd(120) === 1) {
      // Infrequently, rip nodes out of the document entirely.
      return 'document.implementation.createDocument("", "", null).adoptNode(' + commandn2 + ');';
    }

    if (rnd(9) === 3) {
      // Sometimes, use insertBefore.
      // (Not too often; it hurts reduction, and any tree state that can
      // be reached with insertBefore can be reached with a different pattern
      // of appendChild calls.)
      return "iB(" + commandn1 + ", " + commandn2 + ");";
    }

    // Mostly, use appendChild.
    return "aC(" + commandn1 + ", " + commandn2 + ");";
  }

  return { makeCommand: makeCommand };
})();
var fuzzerNewScriptNodes = (function() {

  function makeCommand()
  {
    if (rnd(4) !== 3)
      return []; // silly recursion prevention (e.g. if this fuzzer is used alone)

    var n1index = randomElementIndex();
    if (n1index == null)
      return [];

    var commandn1 = "all.nodes[" + n1index + "]";

    // Add a virgin script node with a script in it.

    // hopefully this will do the right thing -- allow subCommand to reference the new script node and new text node
    // This isn't all that cool; it's possible that it will cause side effects from makeCommand.
    //var oldLength = all.nodes.length;
    //all.nodes[oldLength] = "placeholder";
    //all.nodes[oldLength+1] = "placeholder";

    return 'var ns = document.createElementNS("http://www.w3.org/1999/xhtml", "script"); ' +
           "var nt = document.createTextNode(" + simpleSource(fuzzSubCommand("newscriptnode")) + "); " +
           "ns.appendChild(nt); " +
           commandn1 + ".appendChild(ns);";
  }

  // Two commands inside the script?
  // That would be messy if both commands try to create all.nodes[all.nodes.length].

  // The next thing to try is inserting <script src>, with fast stuff (using data URLs) and
  // slow stuff (using hixie's delay script -- but eep, that sounds like it would introduce nondeterminism)

  return {
    makeCommand: makeCommand,
  };
})();
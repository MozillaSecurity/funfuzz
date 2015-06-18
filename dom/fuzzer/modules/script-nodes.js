var fuzzerNewScriptNodes = (function() {

  function makeCommand()
  {
    if (rnd(4) !== 3)
      return []; // silly recursion prevention (e.g. if this fuzzer is used alone)

    // Add a fresh script node with a script in it.
    // Should probably also generate <script src>

    return 'var ns = document.createElementNS("http://www.w3.org/1999/xhtml", "script"); ' +
           "var nt = document.createTextNode(" + simpleSource(fuzzSubCommand("newscriptnode")) + "); " +
           "ns.appendChild(nt); " +
           Things.instance("Element") + ".appendChild(ns);";
  }

  return {
    makeCommand: makeCommand,
  };
})();

registerModule("fuzzerNewScriptNodes", 3);

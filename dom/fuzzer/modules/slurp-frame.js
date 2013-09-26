// Load a random reftest in a frame, then copy its DOM into the main page.
var fuzzerSlurpFrames = (function() {
  var slurpQueue = [];
  var commandQueue = [];

  function makeCommand()
  {
    if (all.nodes.length > 500)
      return [];

    if (slurpQueue.length && rnd(5)) {
      var n = slurpQueue.shift();
      return "fuzzerSlurpFrames.slurp(" + n + ");";
    }

    while (commandQueue.length) {
      if (rnd(5))
        return commandQueue.shift();
      else
        void commandQueue.shift();
    }

    switch(rnd(6)) {
    case 0:
      var uri = fuzzSrcTreePathToURI(randomThing(fuzzValues.srcTreeReftestFilenames));
      if (uri.substr(0, 5) != "file:" || location.protocol != "file:") {
        // No point loading a non-same-origin page and attempting to slurp it.
        return [];
      }
      var nnindex = all.nodes.length;
      var commandnn = nextSlot("nodes");
      var s = commandnn + ' = document.createElementNS("http://www.w3.org/1999/xhtml", "iframe"); ';
      s += commandnn + ".src = " + simpleSource(uri) + "; ";
      s += "(document.body || document.documentElement).appendChild(" + commandnn + "); ";
      s += "function elv(event) { " + commandnn + ".removeEventListener('load', elv, false); fuzzerSlurpFrames.slurpSoon(" + nnindex + "); }";
      s += commandnn + ".addEventListener('load', elv, false);";
      return s;
    default:
      return [];
    }
  }

  function slurpSoon(n)
  {
    slurpQueue.push(n);
  }

  function slurp(n)
  {
    try {
      var oldAllNodesLength = all.nodes.length;
      var cs = serializeTreeAsScript(all.nodes[n].contentDocument.documentElement);
      var newAllNodesLength = all.nodes.length;

      // Reserve the entire slice
      for (var i = oldAllNodesLength; i < newAllNodesLength; ++i) {
        all.nodes[i] = null;
      }

      for (var i = 0; i < cs.length; ++i) {
        if (cs[i].indexOf("fuzz") != -1)
          cs[i] = "";
        cs[i] = "/*slurped*/ " + cs[i];
      }
      commandQueue.push(cs);
      commandQueue.push("/*slurpDone*/rM(all.nodes[" + n + "]);");
      commandQueue.push("/*slurpInsert*/aC(all.nodes[0], all.nodes[" + oldAllNodesLength + "]);");
      dumpln("Slurped " + (newAllNodesLength - oldAllNodesLength) + " nodes!");
    } catch(e) {
      dumpln("Slurp failure: " + e);
    }
  }

  return { makeCommand: makeCommand, slurpSoon: slurpSoon, slurp: slurp };
})();

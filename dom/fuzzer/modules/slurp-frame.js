// Load a random reftest in a frame, then copy its DOM into the main page.
var fuzzerSlurpFrames = (function() {
  var slurpQueue = [];
  var commandQueue = [];

  function makeCommand()
  {
    if (o.length > 500)
      return [];

    if (slurpQueue.length && rnd(5)) {
      var frameExpr = slurpQueue.shift();
      return "fuzzerSlurpFrames.slurp(" + frameExpr + ");";
    }

    while (commandQueue.length) {
      if (rnd(5))
        return commandQueue.shift();
      else
        void commandQueue.shift();
    }

    switch(rnd(6)) {
    case 0:
      var uri = fuzzSrcTreePathToURI(Random.pick(fuzzValues.srcTreeReftestFilenames));
      if (uri.substr(0, 5) != "file:" || location.protocol != "file:") {
        // No point loading a non-same-origin page and attempting to slurp it.
        return [];
      }
      var newFrame = Things.reserve();
      return [
        newFrame + ' = document.createElementNS("http://www.w3.org/1999/xhtml", "iframe");',
        (
          "function elv(event) { " +
            newFrame + ".removeEventListener('load', elv, false); " +
            "fuzzerSlurpFrames.slurpSoon(" + simpleSource(newFrame) + "); " +
          "} " + newFrame + ".addEventListener('load', elv, false);"
        ),
        newFrame + ".src = " + simpleSource(uri) + ";",
        "(document.body || document.documentElement).appendChild(" + newFrame + ");"
      ];
    default:
      return [];
    }
  }

  function slurpSoon(frameExpr)
  {
    slurpQueue.push(frameExpr);
  }

  function slurp(frameObj)
  {
    try {
      var oldLastIndex = Things._lastIndex;
      var cs = serializeTreeAsScript(frameObj.contentDocument.documentElement);
      var newLastIndex = Things._lastIndex;

      // Undo what serializeTreeAsScript just did, because we want to redo it ourselves.
      // (This is smelly; serializeTreeAsScript should be refactored to handle this use case better.)
      for (var i = oldLastIndex+1; i < newLastIndex+1; ++i) {
        o[i] = null;
      }

      for (var i = 0; i < cs.length; ++i) {
        if (cs[i].indexOf("fuzz") != -1)
          cs[i] = "";
        cs[i] = "/*slurped*/ " + cs[i];
      }
      commandQueue.push(cs);
      if (rnd(2)) {
        commandQueue.push("/*slurpDone*/rM(" + Things.find(frameObj) + ");");
      }
      commandQueue.push("/*slurpInsert*/aC(" + Things.find(document.documentElement) + ", o[" + (oldLastIndex+1) + "]);");
      dumpln("Slurped " + (newLastIndex - oldLastIndex) + " nodes!");
    } catch(e) {
      dumpln("Slurp failure: " + e);
    }
  }

  return { makeCommand: makeCommand, slurpSoon: slurpSoon, slurp: slurp };
})();

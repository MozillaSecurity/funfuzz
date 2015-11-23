var fuzzerChromeCode = (function() {

  function windowSize()
  {
    try {
      return rnd(screen.width + 1) + ", " + rnd(screen.height + 1);
    } catch(e) {
      return "300, 300";
    }
  }

  function makeCommand()
  {
    switch(rnd(50)) {
    case 4:
      return "fuzzPriv.zoom(\"text\", " + (0.1 * (rnd(100) + 1)) + ");";
    case 5:
      return "fuzzPriv.zoom(\"full\", " + (0.1 * (rnd(100) + 1)) + ");";
    case 6:
      if (rnd(200) === 0)
        return "fuzzPriv.printToFile(" + rndBoolStr() + ", " + rndBoolStr() + ", " + rndBoolStr() + ", " + rndBoolStr() + "); interval=3000;";
      return [];
    case 7:
      if (rnd(3) === 0) {
        return "fuzzPriv.getMemoryReports(" + rndBoolStr() + ");";
      }
      return [];
    case 8:
      var flags = rnd(0x20); // http://mxr.mozilla.org/mozilla-central/source/dom/interfaces/canvas/nsIDOMCanvasRenderingContext2D.idl#216
      var scale = rnd(2) ? "null" : (0.01 * (1 + rnd(100))); // https://hg.mozilla.org/mozilla-central/annotate/6d7fae9764b3/browser/components/thumbnails/PageThumbs.jsm#l114
      return "fuzzPriv.callDrawWindow(" + flags + ", " + scale + ");";
    case 9:
      return Random.index(["fuzzPriv", "window"]) + ".resizeTo(" + windowSize() + ");";
    default:
      return [];
    }
  }

  return { makeCommand: makeCommand };
})();

registerModule("fuzzerChromeCode", 5);

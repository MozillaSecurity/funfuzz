var fuzzerComparePixels = (function() {
  function comp()
  {
    var a = [
      "var root = document.documentElement; document.removeChild(root); " + fuzzerGC.immediate() + " document.appendChild(root); ",
      // "document.normalize(); ", // bug 723357, bug 723657 (could use max channel difference instead)
      // "var t = " + Things.instance("Element") + "; var s = t.getAttribute('style'); t.removeAttribute('style'); t.setAttribute('style', s); ", // bug 475216
      fuzzerGC.immediate(),
      "document.documentElement.offsetHeight; ",
      "document.documentElement.getBoundingClientRect(); "
      // Not tested: resize the window and back (better to test this indirectly, I think)
      // Not tested: serializeDOMAsScript / capgras (plenty of state legitimately exists in the DOM)
      // Not tested: re-setting attributes other than style
    ];

    var numToTake = rnd(3) + 1;
    var s = "";
    for (var i = 0; i < numToTake; ++i) {
      // Sample without replacement
      s += a.splice(rnd(a.length), 1)[0];
    }

    return "/*fuzzRepeat*/ (function() { var f = fuzzPriv.comparePixels(); " + s + "var v = f(); if (v) { dumpln('Rendered inconsistently: ' + v); } else { dumpln('Match.'); } })();";
  }

  function makeCommand()
  {
    if (rnd(30) === 0)
      return comp();
    return [];
  }
  return { makeCommand: makeCommand };
})();
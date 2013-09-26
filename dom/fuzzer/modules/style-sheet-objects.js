var fuzzerDOMCSS = (function() {

  // http://www.w3.org/TR/DOM-Level-2-Style/css

  // Both CSSStyleSheet and CSSGroupingRule have "deleteRule", "insertRule", and "cssRules" properties.
  // Because of this, we're happy to have stylesheets in all.CSSRules

  function varss()
  {
    if (all.CSSRules.length && rnd(2))
      return "var ss = " + pick("CSSRules") + "; ";

    var ssl = document.styleSheets.length;
    if (ssl == 0)
      return ""; // no sheets to play with :(
    var ssn = rnd(ssl);
    return "var ss = document.styleSheets[" + ssn + "]; ";
  }

  function makeCommand()
  {
    if (rnd(100) === 0) {
      // trigger nsStyleSet::GCRuleTrees
      return "for (var collectMe = 0; collectMe < 305; ++collectMe) { document.documentElement.style.color = (i%2)?'red':''; document.documentElement.offsetHeight; }";
    }
    if (rnd(100) === 0) {
      return "document.documentElement.offsetHeight;";
    }

    switch(rnd(8)) {
    case 0:
      // delete a rule
      return varss() + "ss.deleteRule(" + rnd(10000) + " % ss.cssRules.length);";
    case 1:
      // insert a new rule
      return varss() + "ss.insertRule(" + simpleSource(fuzzerRandomClasses.randomRule()) + ", " + rnd(10000) + " % (ss.cssRules.length+1));";
    case 2:
      // append a rule
      // (CSSKeyframesRule has appendRule instead of insertRule, because order doesn't matter)
      return varss() + "ss.appendRule(" + simpleSource(fuzzerRandomClasses.randomRule()) + ");";
    case 3:
      // loop over all rules, doing SOMETHING...
      var sc = fuzzSubCommand();
      if (sc.indexOf("fuzzRepeat") != -1 || sc.indexOf("insertRule") != -1) // avoid nested loops, variable confusion, infinite loops
        sc = rnd(2) ? "/*DOMCSS-sanity*/" : "return;";
      if (rnd(2) === 1)
        sc = "if (fuzzRepeat == " + rnd(500) + ") { " + sc + "}"; // only do it once
      // pick an insertion point
      var sca = ["","","",""];
      sca[rnd(4)] = sc;
      return varss() + "for (var fuzzRepeat = 0; fuzzRepeat < ss.cssRules.length; ++fuzzRepeat) { " + sca[0] + "; var rule = ss.cssRules[fuzzRepeat]; " + sca[1] + "; rule.selectorText; " + sca[2] + "; rule.cssText; " + sca[3] + " }";
    case 4:
      // read from a rule
      if (all.CSSRules.length) {
        return addIfNovel("strings", pick("CSSRules") + "." + rndElt(["selectorText", "cssText"]));
      }
    case 5:
      // grab a rule
      return varss() + addIfNovel("CSSRules", "ss.cssRules[" + rnd(10000) + " % ss.cssRules.length]");
    case 6:
      // grab a CSSStyleSheet object from a HTMLStyleElement (as long as the HTMLStyleElement is in a document)
      return addIfNovel("CSSRules", pick("nodes") + ".sheet");
    default:
      // stash a stylesheet -- possibly one that will be removed from the document, or possibly from another document
      return addIfNovel("CSSRules", pick("documents") + ".styleSheets[0]");
    }

    return [];
  }

  return {
    makeCommand: makeCommand,
  };
})();
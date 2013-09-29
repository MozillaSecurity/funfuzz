var fuzzerDOMCSS = (function() {

  // http://www.w3.org/TR/DOM-Level-2-Style/css

  function anyRuleGroup()
  {
    return rnd(2) ? Things.instance("CSSGroupingRule") : Things.instance("CSSStyleSheet");
  }

  function varRG()
  {
    return "var rg = " + anyRuleGroup() + "; ";
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
      return varRG() + "rg.deleteRule(" + rnd(10000) + " % rg.cssRules.length);";
    case 1:
      // insert a new rule
      return varRG() + "rg.insertRule(" + simpleSource(fuzzerRandomClasses.randomRule()) + ", " + rnd(10000) + " % (rg.cssRules.length+1));";
    case 2:
      // append a rule
      // (CSSKeyframesRule has appendRule instead of insertRule, because order doesn't matter)
      return varRG() + "rg.appendRule(" + simpleSource(fuzzerRandomClasses.randomRule()) + ");";
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
      return varRG() + "for (var fuzzRepeat = 0; fuzzRepeat < rg.cssRules.length; ++fuzzRepeat) { " + sca[0] + "; var rule = rg.cssRules[fuzzRepeat]; " + sca[1] + "; rule.selectorText; " + sca[2] + "; rule.cssText; " + sca[3] + " }";
    case 4:
      // read from a rule
      return Things.add(Things.instance("CSSStyleRule") + "." + rndElt(["selectorText", "cssText"]));
    case 5:
      // grab a rule
      return varRG() + Things.add("rg.cssRules[" + rnd(10000) + " % rg.cssRules.length]");
    case 6:
      // Grab a CSSStyleSheet object from a HTMLStyleElement (as long as the HTMLStyleElement is in a document)
      return Things.add(Things.instance("HTMLStyleElement") + ".sheet");
    default:
      // Grab a CSSStyleSheet object -- possibly one that will be removed from the document, or possibly from another document
      return Things.add(Things.instance("Document") + ".styleSheets[0]");
    }

    return [];
  }

  return {
    makeCommand: makeCommand,
  };
})();
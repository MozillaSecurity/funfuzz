var fuzzerRandomStyles = (function() {

  function pickTarget()
  {
    if (all.CSSStyleDeclarations.length && rnd(2)) {
      return pick("CSSStyleDeclarations");
    }

    return "all.nodes[" + randomElementIndex() + "].style";
  }

  function makeCommand() {
    if (rnd(3000) === 0)
      return (rnd(2) ? pick("documents") : pick("nodes")) + ".dir = \"" + rndElt(["ltr", "rtl", "auto"]) + "\";";

    var decl = fuzzerRandomClasses.randomDeclaration();
    var target = pickTarget();
    return target + "." + domifyCSSProperty(decl.prop) + " = " + simpleSource(decl.value) + ";";
  }

  function domifyCSSProperty(prop)
  {
    if (prop == "float")
      return "cssFloat";
    else
      return prop.replace(/-[a-z]/g, function(s) { return s.charAt(1).toUpperCase(); });
  }

  return { makeCommand: makeCommand };
})();
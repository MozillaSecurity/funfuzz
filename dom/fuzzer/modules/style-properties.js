var fuzzerRandomStyles = (function() {

  function makeCommand() {
    if (rnd(3000) === 0)
      return (rnd(2) ? Things.instance("Document") : Things.instance("HTMLElement")) + ".dir = \"" + Random.index(["ltr", "rtl", "auto"]) + "\";";

    var target = Things.instance("CSSStyleDeclaration");
    if (target == "o[-1]" || rnd(2)) {
      return Things.add(Things.instance("Element") + ".style")
    }

    var decl = fuzzerRandomClasses.randomDeclaration();

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

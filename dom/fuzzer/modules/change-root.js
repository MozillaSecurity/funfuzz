var fuzzerChangeRoot = (function() {
  function makeCommand() {
    if (novel(document)) {
      // Expose document node to StirDOM
      return nextSlot("nodes") + " = document;";
    } else if (document.documentElement) {
      return "document.removeChild(document.documentElement);";
    } else {
      var n1index = randomElementIndex();
      if (n1index == null)
        return [];
      var commandn1 = "all.nodes[" + n1index + "]";
      return "document.appendChild(" + commandn1 + ");";
    }
  }

  return { makeCommand: makeCommand };
})();

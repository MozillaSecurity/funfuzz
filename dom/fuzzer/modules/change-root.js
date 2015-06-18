var fuzzerChangeRoot = (function() {
  function makeCommand() {
    if (document.documentElement) {
      return "document.removeChild(document.documentElement);";
    } else {
      return "document.appendChild(" + Things.instance("Element") + ");";
    }
  }

  return { makeCommand: makeCommand };
})();

registerModule("fuzzerChangeRoot", 2);

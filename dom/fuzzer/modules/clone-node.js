var fuzzerCloneNode = (function() {
  function makeCommand() {
    var n2index = Things.instanceIndex("Node");
    var commandn2 = "o[" + n2index + "]";
    var n2 = o[n2index];

    var deep = Random.index(["true", "false"]);

    try {
      if (n2.getElementsByTagName("*").length > 20) {
        deep = "false";
      }
    } catch(e) {
      return [];
    }

    var newb = Things.reserve();

    return [
      newb + " = " + commandn2 + ".cloneNode(" + deep + ");",
      Things.instance("Element") + ".appendChild(" + newb + ");"
    ];
  }

  return { makeCommand: makeCommand };
})();

registerModule("fuzzerCloneNode", 1);

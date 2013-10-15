var fuzzerRangeAndSelection = (function() {
  var tempNodeIndex;

  var rangeMethods = [
    {name: "setStart", retobj: null, args: [makeRndNodeRef, rndOffsetRndNode]},
    {name: "setEnd", retobj: null, args: [makeRndNodeRef, rndOffsetRndNode]},
    {name: "setStartBefore", retobj: null, args: [makeRndNodeRef]},
    {name: "setStartAfter", retobj: null, args: [makeRndNodeRef]},
    {name: "setEndBefore", retobj: null, args: [makeRndNodeRef]},
    {name: "setEndAfter", retobj: null, args: [makeRndNodeRef]},
    {name: "selectNode", retobj: null, args: [makeRndNodeRef]},
    {name: "selectNodeContents", retobj: null, args: [makeRndNodeRef]},
    {name: "collapse", retobj: null, args: ["true", "false"]},
    {name: "cloneContents", retobj: "DocumentFragment", args: []},
    {name: "deleteContents", retobj: null, args: []},
    {name: "extractContents", retobj: "DocumentFragment", args: []},
    {name: "insertNode", retobj: null, args: [makeRndNodeRef]},
    {name: "surroundContents", retobj: null, args: [makeRndNodeRef]},
    {name: "compareBoundaryPoints", retobj: null, args: [[Range.START_TO_END, Range.START_TO_START, Range.END_TO_START, Range.END_TO_END], randomRange]},
    {name: "cloneRange", retobj: null, args: []},
    {name: "detach", retobj: null, args: []} // removed in bug 702948 for mozilla 15
  ];

  function randomRange()
  {
    return Things.instance("Range");
  }

  function makeRndNodeRef()
  {
    // Store tempNodeIndex so rndOffsetRndNode can use it
    tempNodeIndex = Things.instanceIndex("Node");
    return "o[" + tempNodeIndex + "]";
  }
  function rndOffsetRndNode()
  {
    return rnd(offsets(o[tempNodeIndex]));
  }

  function makeNewRange()
  {
    var n1i = Things.instanceIndex("Node");
    var n2i = Things.instanceIndex("Node");

    var rangeStr = Things.reserve();

    return [
      rangeStr + " = document.createRange();",
      rangeStr + ".setStart(o[" + n1i + "], " + rnd(offsets(o[n1i])) + "); ",
      rangeStr +   ".setEnd(o[" + n2i + "], " + rnd(offsets(o[n2i])) + "); "
    ];
  }

  function offsets(n)
  {
    if (n) {
      try {
        if (n.nodeType == Node.TEXT_NODE)
          return n.data.length + 1;
        else
          return n.childNodes.length + 1;
      } catch(e) {
        // Catch e.g. due to fuzzerRandomJS screwing with us.
        dumpln("Warning: offsets() is confused");
        return 1;
      }
    }
    else {
      return 1;
    }
  }

  // http://dvcs.w3.org/hg/editing/raw-file/tip/editing.html#selections
  // Plus two non-standard methods, selectionLanguageChange() and modify()
  var selectionMethods = [
    {name: "getRangeAt", retobj: "Range", args: [[0, [1, 2, 3, 4, 5, 6]]]},
    {name: "collapse", retobj: null, args: [makeRndNodeRef, rndOffsetRndNode]},
    {name: "extend", retobj: null, args: [makeRndNodeRef, rndOffsetRndNode]},
    {name: "collapseToStart", retobj: null, args: []},
    {name: "collapseToEnd", retobj: null, args: []},
    {name: "selectAllChildren", retobj: null, args: [makeRndNodeRef]},
    {name: "addRange", retobj: null, args: [function(){return Things.instance("Range"); }]},
    {name: "removeRange", retobj: null, args: [function(){return Things.instance("Range"); }]},
    {name: "removeAllRanges", retobj: null, args: []},
    {name: "deleteFromDocument", retobj: null, args: []},
    {name: "toString", retobj: null, args: []},
    {name: "containsNode", retobj: null, args: [makeRndNodeRef, ["true", "false"]]},
    {name: "selectionLanguageChange", retobj: null, args: ["true", "false"]},
    {name: "modify", retobj: null, args: [['"extend"', '"move"'], ['"forward"', '"backward"', '"left"', '"right"'], ['"character"', '"word"', '"sentence"', '"line"', '"paragraph"', '"lineboundary"', '"sentenceboundary"', '"paragraphboundary"', '"documentboundary"']]},
  ];

  function callStr(subject, method)
  {
    var args = method.args;

    var callStr = subject + "." + method.name + "(";
    for (var b = 0; b < args.length; ++b)
      callStr += Random.pick(args[b]) + (b+1 == args.length ? "" : ", ");
    callStr += ")";

    if (method.retobj) {
      return Things.add(callStr);
    } else {
      return callStr + ";";
    }
  }

  function makeCommand()
  {
    switch(rnd(6)) {
    case 0:
      // Make a Range.
      return makeNewRange();

    case 1:
      // Call a random method of a Range.
      var method = Random.index(rangeMethods);
      return callStr(Things.instance("Range"), method);

    case 2:
      // Grab a Selection.
      return Things.add(Things.instance("Window") + ".getSelection()")

    case 3:
      // Call a random method of a Selection.
      var method = Random.index(selectionMethods);
      return callStr(Things.instance("Selection"), method);

    case 4:
      // Call window.find(), which can affect the selection.
      // (If bug 672395 gets fixed, this will need to move into fuzzPriv.)
      var findText = Random.pick(fuzzValues.texts);
      var caseSensitive = rnd(2) === 1;
      var backwards = rnd(2) === 1;
      var wraparound = rnd(2) === 1;
      var wholeWord = rnd(2) === 1;
      var includeFrames = rnd(2) === 1;
      var showDialog = rnd(10000) === 1;
      return Things.instance("Window") + ".find(" + simpleSource(findText) + ", " + caseSensitive + ", " + backwards + ", " + wraparound + ", " + wholeWord + ", " + includeFrames + ", " + showDialog + ");";

    default:
      // Grab anchorNode or focusNode
      return Things.add(Things.instance("Range") + "." + Random.index(["anchorNode", "focusNode"]));
    }
  }

  return { makeCommand: makeCommand };
})();

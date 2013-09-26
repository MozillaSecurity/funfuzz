var fuzzerRangeAndSelection = (function() {
  var tempNodeIndex;

  // cloneContents and extractContents return DocumentFragment objects, which we stick into all.nodes.

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
    {name: "cloneContents", retobj: "nodes", args: []},
    {name: "deleteContents", retobj: null, args: []},
    {name: "extractContents", retobj: "nodes", args: []},
    {name: "insertNode", retobj: null, args: [makeRndNodeRef]},
    {name: "surroundContents", retobj: null, args: [makeRndNodeRef]},
    {name: "compareBoundaryPoints", retobj: null, args: [[Range.START_TO_END, Range.START_TO_START, Range.END_TO_START, Range.END_TO_END], randomRange]},
    {name: "cloneRange", retobj: null, args: []},
    {name: "detach", retobj: null, args: []} // removed in bug 702948 for mozilla 15
  ];

  function randomRange()
  {
    if (all.ranges.length)
      return pick("ranges");
    else
      return "null";
  }

  function makeRndNodeRef()
  {
    // Store tempNodeIndex so rndOffsetRndNode can use it
    tempNodeIndex = rnd(all.nodes.length);
    return "all.nodes[" + tempNodeIndex + "]";
  }
  function rndOffsetRndNode()
  {
    return rnd(offsets(all.nodes[tempNodeIndex]));
  }

  function makeNewRange()
  {
    var n1 = rnd(all.nodes.length);
    var n2 = rnd(all.nodes.length);

    var rangeStr = nextSlot("ranges");

    return [
      rangeStr + " = document.createRange();",
      rangeStr + ".setStart(all.nodes[" + n1 + "], " + rnd(offsets(all.nodes[n1])) + "); ",
      rangeStr +   ".setEnd(all.nodes[" + n2 + "], " + rnd(offsets(all.nodes[n2])) + "); "
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
    {name: "getRangeAt", retobj: "ranges", args: [[0, [1, 2, 3, 4, 5, 6]]]},
    {name: "collapse", retobj: null, args: [makeRndNodeRef, rndOffsetRndNode]},
    {name: "extend", retobj: null, args: [makeRndNodeRef, rndOffsetRndNode]},
    {name: "collapseToStart", retobj: null, args: []},
    {name: "collapseToEnd", retobj: null, args: []},
    {name: "selectAllChildren", retobj: null, args: [makeRndNodeRef]},
    {name: "addRange", retobj: null, args: [function(){return pick("ranges"); }]},
    {name: "removeRange", retobj: null, args: [function(){return pick("ranges"); }]},
    {name: "removeAllRanges", retobj: null, args: []},
    {name: "deleteFromDocument", retobj: null, args: []},
    {name: "toString", retobj: null, args: []},
    {name: "containsNode", retobj: null, args: [makeRndNodeRef, ["true", "false"]]},
    {name: "selectionLanguageChange", retobj: null, args: ["true", "false"]},
    {name: "modify", retobj: null, args: [['"extend"', '"move"'], ['"forward"', '"backward"', '"left"', '"right"'], ['"character"', '"word"', '"sentence"', '"line"', '"paragraph"', '"lineboundary"', '"sentenceboundary"', '"paragraphboundary"', '"documentboundary"']]},
  ];

  function win()
  {
    return pick("windows");
  }

  function callStr(subject, method)
  {
    var args = method.args;

    var callStr = subject + "." + method.name + "(";
    for (var b = 0; b < args.length; ++b)
      callStr += randomThing(args[b]) + (b+1 == args.length ? "" : ", ");
    callStr += ")";

    if (method.retobj) {
      return addIfNovel(method.retobj, callStr);
    } else {
      return callStr + ";";
    }
  }

  function makeCommand()
  {
    switch(rnd(5)) {
    case 0:
      // Add a random range to all.ranges
      return makeNewRange();

    case 1:
      // Call a random method of a range.

      if (all.ranges.length) {
        var method = rndElt(rangeMethods);
        return callStr(pick("ranges"), method);
      }

    case 2:
      // Call a random method of getSelection().

      var method = rndElt(selectionMethods);
      return callStr(win() + ".getSelection()", method);

    case 3:
      // Call window.find(), which can affect the selection.
      // (If bug 672395 gets fixed, this will need to move into fuzzPriv.)
      var findText = randomThing(fuzzValues.texts);
      var caseSensitive = rnd(2) === 1;
      var backwards = rnd(2) === 1;
      var wraparound = rnd(2) === 1;
      var wholeWord = rnd(2) === 1;
      var includeFrames = rnd(2) === 1;
      var showDialog = rnd(10000) === 1;
      return win() + ".find(" + simpleSource(findText) + ", " + caseSensitive + ", " + backwards + ", " + wraparound + ", " + wholeWord + ", " + includeFrames + ", " + showDialog + ");";
    default:
      // Grab anchorNode or focusNode
      if (all.ranges.length) {
        return nextSlot("nodes") + " = " + pick("ranges") + "." + rndElt(["anchorNode", "focusNode"]) + ";";
      }
    }
  }

  return { makeCommand: makeCommand };
})();

var fuzzerStirTable = (function() {

  // Subset of Random Classes style properties.
  var tableRelatedCSSProperties = [
    {
      prop: "display",
      values: [
      // Basic
      "inline", "block", "inline-block", "inline-table", "list-item",
      // Table display values
      "table", "table-caption",
      "table-row-group", "table-header-group", "table-footer-group",
      "table-row", "table-cell",
      "table-column", "table-column-group",
      ]
    },
    {
      prop: "float",
      values: ["left", "right", "none"]
    },
    {
      prop: "borderCollapse",
      values: ["inherit", "separate", "collapse"]
    },
    {
      prop: "captionSide",
      values: ["inherit", "right", "left", "top", "bottom"]
    },
    {
      prop: "emptyCells",
      values: ["inherit", "show"]
    },
    {
      prop: "tableLayout",
      values: ["fixed", "auto"]
    },
    {
      prop: "visibility",
      values: ["visible", "hidden", "collapse"]
    },
    {
      prop: "position",
      values: ["static", "relative", "absolute", "fixed", "sticky"]
    },
    {
      prop: "overflow",
      values: ["visible", "scroll", "hidden", "auto", "-moz-scrollbars-horizontal", "-moz-scrollbars-none", "-moz-scrollbars-vertical", "-moz-hidden-unscrollable"]
    },
    {
      prop: "direction",
      values: ["inherit", "ltr", "rtl"]
    },
    {
      prop: "border",
      values: ["1px solid green", "2px dotted yellow", "3px double red", "6px inset green", "7px solid pink", "none"]
    },
    {
      prop: "borderLeft",
      values: ["1px solid green", "2px dotted yellow", "3px double red", "6px inset green", "7px solid pink", "none"]
    },
    {
      prop: "borderRight",
      values: ["1px solid green", "2px dotted yellow", "3px double red", "6px inset green", "7px solid pink", "none"]
    },
    {
      prop: "borderBottom",
      values: ["1px solid green", "2px dotted yellow", "3px double red", "6px inset green", "7px solid pink", "none"]
    },
    {
      prop: "borderTop",
      values: ["1px solid green", "2px dotted yellow", "3px double red", "6px inset green", "7px solid pink", "none"]
    },
    {
      prop: "outline",
      values: ["7px dotted pink", "none"]
    },
    {
      prop: "width",
      values: ["0", "1px", "18px", "100px", "1200px",
        "-moz-max-content", "-moz-min-content", "-moz-available", "-moz-fit-content"]
    }


  ];


  var lengthUnits = ['','%','px','em'];
  var lengthValues = ['0','1','13','50','99','100'];

  function rndWHV(elemVar, elem, tag) {
    var commands = [];

    if (rnd(3) === 0)
      commands.push(elemVar + ".setAttribute('width', '"  + Random.index(lengthValues) + Random.index(lengthUnits) + "');");

    if (rnd(3) === 0)
      commands.push(elemVar + ".setAttribute('height', '" + Random.index(lengthValues) + Random.index(lengthUnits) + "');");

    while (rnd(3) === 0)
      commands.push(change_style(elemVar, elem, tag));

    return commands;
  }

  var elementsWantingChildren = [];

  // This doesn't include rowspan/colspan/span -- those are handled separately.
  var attributeInfo = {
    align: [
      "top", "bottom", "left", "right", // for caption
      "left", "right", "center", "justify", "char" // for most other things
      ],
    dir: ["ltr", "rtl", "auto"],
    width: [
      "0*", "100px", "50px 50px 50px", "30% 30% 30%", "30% 30% 30% 30%", // for colgroup and col
      "0", "4", "100", "1000", "20%", "100%" // for other things
      ],
    frame: ["void", "above", "below", "hsides", "lhs", "rhs", "vsides", "box", "border"],
    rules: ["none", "groups", "rows", "cols", "all"],
    border: ["0", "1", "2", "10"],
    cellspacing: ["0", "1", "5", "6"],
    cellpadding: ["0", "1", "5", "6"]
  };

  var allAttributes = [];
  for (var attrX in attributeInfo)
    allAttributes.push(attrX);

  var tagInfo =
  {
    td:       { spans: true,  children: ["text", "div", "span", "table"] },
    th:       { spans: true,  children: ["text", "div", "span", "table"] },

    tr:       { spans: false, children: ["td", "th"] },

    thead:    { spans: false, children: ["tr"] },
    tbody:    { spans: false, children: ["tr"] },
    tfoot:    { spans: false, children: ["tr"] },

    caption:  { spans: false, children: ["text", "div", "span", "table"], attributes: ["align"] },

    // I'm not sure about these, especially the "spans" part...
    // "span" attribute instead of "colspan" attribute?
    colgroup: { spans: true,  children: ["col"], attributes: ["width"] },
    col:      { spans: true,  children: [], attributes: ["width"] },

    table:    { spans: false, children: ["tr", "tr", "tr", "thead", "tbody", "tfoot", "caption", "colgroup"], attributes: ["dir", "frame", "border", "cellspacing", "cellpadding", "width"] },

    div:      { spans: false, children: ["text", "div", "span", "table"] },
    span:     { spans: false, children: ["text", "div", "span", "table"] } // span-containing-div causes special code to execute, so it definitely shouldn't be discouraged
  };

  var tableRelatedTags = [];
  for (var tagX in tagInfo)
    tableRelatedTags.push(tagX);




  function insertNewInto(elemVar, elem, tag)
  {
    var commands = [];

    if (!elem || !elem.tagName)
      return "/* stirtable is confused */";

    var parentTag = elem.tagName.toLowerCase();


    // Usually choose a tag based on the list of "likely child tags" for tagInfo, but sometimes choose a tag completely at random.
    var preferredChildTags = (tagInfo[parentTag] || tagInfo["div"]).children;

    var childTag;

    if (elemVar == rootD) {
      childTag = "table";
    } else {
      if (preferredChildTags.length !== 0 && rnd(5) !== 1)
        childTag = Random.index(preferredChildTags);
      else
        childTag = Random.index(tableRelatedTags);

      if (childTag == "table") {
        // Don't make nested tables too often.
        if (rnd(10) !== 1)
          childTag = "text";
      }
    }

    var neVar = Things.reserve();

    if (childTag == "text") {
      commands.push(neVar + " = document.createTextNode('" + parentTag + "');");
    } else {
      commands.push(neVar + " = document.createElementNS('http://www.w3.org/1999/xhtml', '" + childTag + "');");

      commands = commands.concat(rndWHV(neVar, null, childTag));

      if (childTag in tagInfo && tagInfo[childTag].spans) {
        if (rnd(3) === 0)
          commands.push(change_rowspan(neVar, null, childTag));
        if (rnd(3) === 0)
          commands.push(change_colspan(neVar, null, childTag));
      }
      commands.push("fuzzerStirTable.bless(" + neVar + ");");
    }


    // Decide where to put it and stick it in.

    var sib = elem.firstChild ? Random.index(elem.childNodes) : null;
    var sibIndex = Things.findIndex(sib);
    var sibExpr = (sibIndex !== -1) ? ("o[" + sibIndex + "]") : null;
    commands.push(elemVar + ".insertBefore(" + neVar + ", " + sibExpr + ");");

    return commands;
  }

  // This strange function is called *by* randomly generated functions, and is used only to *influence* future randomly generated functions.
  function bless(newNode)
  {
    if (newNode.nodeType != 1)
      return;

    var numChildrenWanted;

    var ti = tagInfo[newNode.tagName.toLowerCase()];

    if (ti && ti.children.length)
      numChildrenWanted = Random.index([0, 0, 1, 1, 1, 1, 2]);
    else
      numChildrenWanted = Random.index([0, 0, 0, 0, 0, 0, 1]);

    for (var i = 0; i < numChildrenWanted; ++i) {
      elementsWantingChildren.push(newNode);
    }
  }


  function remove(elemVar, elem, tag) {
    if (tag == "html" || tag == "body" || tag == "head" || tag == "style")
      return "/* stirtable being nice */";

    if (tag == "table" || tag == "div")
      return "/* stirtable being careful */";

    return "rM(" + elemVar + ");";
  }

  function change_style(elemVar, elem, tag) {
    var propPair = Random.index(tableRelatedCSSProperties);
    var prop = propPair.prop;
    var value;

    if (rnd(3) === 1)
      value = Random.index(["", "inherit", "initial", "auto"]);
    else
      value = Random.index(propPair.values);

    return elemVar + ".style." + prop + " = " + simpleSource(value) + ";";
  }

  function change_attribute(elemVar, elem, tag) {
    var attrs = (tagInfo[tag] || tagInfo["div"]).attributes;
    if (!attrs || rnd(5) === 1)
      attrs = allAttributes;
    var attr = Random.index(attrs);

    if (rnd(3)) {
      var value = Random.index(attributeInfo[attr]);
      return elemVar + ".setAttribute(" + simpleSource(attr) + ", " + simpleSource(value) + ");";
    } else {
      return elemVar + ".removeAttribute(" + simpleSource(attr) + ");";
    }
  }

  function change_rowspan(elemVar, elem, tag) {
    var rowspanX = simpleSource(Random.pick(fuzzValues.tableSpans));
    return elemVar + ".setAttribute('rowspan', " + rowspanX + ");";
  }

  function change_colspan(elemVar, elem, tag) {
    var colspanX = simpleSource(Random.pick(fuzzValues.tableSpans));

    if (tag.toLowerCase() == 'col' || tag.toLowerCase() == 'colgroup')
      return elemVar + ".setAttribute('span', " + colspanX + ");";
    else
      return elemVar + ".setAttribute('colspan', " + colspanX + ");";
  }


  // ops are functions: (elemVar, possibly null elem, tag) -> command string or command string array
  // Gah!  Which of these things do I actually need?  *Then* rewrite makeCommand.
  // I think that only insertNewInto uses elem... but you need elem to get tag... so maybe this is fine.

  var ops = [insertNewInto, remove, change_rowspan, change_colspan, change_style, change_attribute];

  function getTableRelatedVictim()
  {
    var tag = Random.index(tableRelatedTags);
    var elems = document.getElementsByTagName(tag);
    if (elems.length)
      return Random.index(elems);
    else
      return null;
  }

  var rootD = "(document.body || document.documentElement)";
  function rootDE() { return document.body || document.documentElement; }


  function makeCommand() {

    var command = "";

    var elem, elemVar, elemIndex, op;

    if (document.getElementsByTagName("table").length === 0) {
      // Create a top-level table?
      elem = rootDE();
      elemVar = rootD;
      if (!elem)
        return "/* stirtable -- completely empty document */";
      op = insertNewInto;
    } else if (elementsWantingChildren.length) {
      // Pop off an element, and make a child for it.
      elem = elementsWantingChildren.pop();
      elemIndex = Things.findIndex(elem);
      elemVar = "o[" + elemIndex + "]";
      op = insertNewInto;
    } else if (rnd(19) !== 1 && (elem = getTableRelatedVictim())) { // prefer table-related, present elements
      elemIndex = Things.findIndex(elem);
      if (elemIndex === -1)
        return "/* stirtable's victim (" + elem.tagName + ") is hiding */";
      elemVar = "o[" + elemIndex + "]";
      op = Random.index(ops);
    } else {
      // Pick an operation and a victim at random.
      elemIndex = Things.instanceIndex("Element");
      if (elemIndex === -1)
        return "/* stirtable couldn't find a victim */";
      elem = o[elemIndex];
      elemVar = "o[" + elemIndex + "]";
      op = Random.index(ops);
    }

    if (elem.tagName) {
      // pass lots of seemingly redundant information: a variable name for the element, the element, and its tagName!!
      return op(elemVar, elem, elem.tagName.toLowerCase());
    } else {
      return "/* wtf4 */"; // e.g. due to RandomJS
    }
  }


  return {
    makeCommand: makeCommand,
    newb: null,
    bless: bless
  };

})();

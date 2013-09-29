var fuzzerMathMLAttributes = (function() {

  function several(pickArg)
  {
    return function() {
      var num = Random.pick([0, 1, [2, 4, 8, 16, 1024]]);
      var s = "";
      for (var i = 0; i < num; ++i) {
        if (i != 0)
          s += " ";
        s += Random.pick(pickArg);
      }
      return s;
    };
  }

  var tableAligns = ["top", "bottom", "center", "baseline", "axis"];
  function tableAlignAttr() { return Random.index(tableAligns) + Random.index(["", " " + Random.pick(fuzzValues.numbers)]); }
  var horizAligns = ["left", "center", "right"];
  var lines = ["none", "solid", "dashed"];

  function mpaddedAttr() {
    // Note from spec:
    // "Note that the examples in the Version 2 of the MathML specification showed spaces within the attribute values,
    // suggesting that this was the intended format. Formally, spaces are not allowed within these values, but
    // implementers may wish to ignore such spaces to maximize backward compatibility."
    return (
      Random.index(["+", "-", ""]) +
      Random.pick(fuzzValues.unsignedNumbers) +
      (rnd(2) ? Random.index(["%", "%width", "%height", "%depth", "width", "height", "depth", "mediummathspace", "negativemediummathspace"]) : Random.pick(fuzzValues.units))
    );
  }

  var commonAttributes = ["id", "mathcolor", "mathbackground", "mathvariant"];

  var attributes = {
    "randomness": fuzzTotallyRandomValue,


    "id": fuzzValues.names,
    "name": fuzzValues.names,

    // annotation, annotation-xml
    "encoding": ["MathML-Presentation", "Mathematica", "Maple", "TeX", "ASCII", "MathMLType", "OpenMath", "content-MathML"],

    // New in MathML 2!
    "mathbackground": fuzzValues.colors,
    "mathcolor": fuzzValues.colors,
    "mathsize": ["small", "normal", "big", fuzzValues.numbersWithUnits],
    "mathvariant": ["normal", "bold", "italic", "bold-italic", "double-struck", "bold-fraktur", "script", "bold-script", "fraktur", "sans-serif", "bold-sans-serif", "sans-serif-italic", "sans-serif-bold-italic", "monospace"],


    // all tokens
    "fontsize": fuzzValues.numbersWithUnits,
    "fontweight": ["normal", "bold"],
    "fontstyle": ["normal", "italic"],
    "fontfamily": [fuzzValues.fontFaces, "inherit"],
    "color": fuzzValues.colors,

    // mo
    "form": ["prefix", "postfix", "infix"],
    "fence": fuzzValues.booleans,
    "separator": fuzzValues.booleans,
    "lspace": [fuzzValues.numbersWithUnits, mpaddedAttr], // also mpadded
    "rspace": fuzzValues.numbersWithUnits,
    "stretchy": fuzzValues.booleans,
    "symmetric": fuzzValues.booleans,
    "maxsize": ["infinity", fuzzValues.numbersWithUnits],
    "minsize": fuzzValues.numbersWithUnits,
    "largeop": fuzzValues.booleans,
    "movablelimits": fuzzValues.booleans,
    "accent": fuzzValues.booleans,

    // mspace, mpadded
    "width": [fuzzValues.numbersWithUnits, mpaddedAttr],
    "height": [fuzzValues.numbersWithUnits, mpaddedAttr],
    "depth": [fuzzValues.numbersWithUnits, mpaddedAttr],
    "voffset": [fuzzValues.numbersWithUnits, mpaddedAttr],

    // ms
    "lquote": ["&quot;", "\"", "\'"],
    "rquote": ["&quot;", "\"", "\'"],


    // mfrac
    "linethickness": [0, 1, 2, 3, "thin", "medium", "thick"],

    // mstyle
    "scriptlevel": ["", "15", "+15", "+5", "-5", "+1", "-1", "3", fuzzValues.numbers],
    "displaystyle": fuzzValues.booleans,
    "scriptsizemultiplier": ["0.71", fuzzValues.numbers],
    "scriptminsize": fuzzValues.numbersWithUnits,
    "background": [fuzzValues.colors, "transparent"],

    // mfenced
    "open": ["<", "(", "[", "{", "|", "f", ""],
    "close": ["<", "(", "[", "{", "|", "g", ""],
    "separators": [",", "", ";", ",;"],

    // msub, msup
    "subscriptshift": fuzzValues.numbersWithUnits,
    "superscriptshift": fuzzValues.numbersWithUnits,

    // mover, munder
    "accentunder": fuzzValues.booleans,

    // mtable
    "align": tableAlignAttr,
    "rowalign": several(tableAligns),
    "columnalign": horizAligns,
    // "groupalign": [groupAlignmentListList, groupAlignmentList], // list of lists for mtable, fewer for mtr or mtd
    "alignmentscope": several(fuzzValues.booleans),
    "rowspacing": fuzzValues.numbersWithUnits,
    "columnspacing": fuzzValues.numbersWithUnits,
    "rowlines": several(lines),
    "columnlines": several(lines),
    "frame": lines,
    "framespacing": function() { return Random.pick(fuzzValues.numbersWithUnits) + " " + Random.pick(fuzzValues.numbersWithUnits); },
    "equalrows": fuzzValues.booleans,
    "equalcolumns": fuzzValues.booleans,

    "rowspan": fuzzValues.tableSpans,
    "columnspan": fuzzValues.tableSpans,

    "notation": function() {
      var notations = ["longdiv", "actuarial", "radical", "box", "roundedbox", "circle", "left", "right", "top", "bottom", "updiagonalstrike", "downdiagonalstrike", "verticalstrike", "horizontalstrike", "madruwb"];
      var n = rnd(2) ? 1 : rnd(10);
      var a = [];
      for (var i = 0; i < n; ++i)
        a.push(Random.index(notations));
      return a.join(" ");
    },

    // maction
    "actiontype": ["toggle", "statusline", "tooltip", "input"],
    "selection": [[1, 2, 3], fuzzValues.numbers],
  };




  // When creating new non-token elements, fill them with new tokens, I guess.

  var elementsX =
  {
    "semantics":       { children: "normal", attributes: [] },
    "annotation":      { children: "normal", attributes: ["encoding"] },
    "annotation-xml":  { children: "normal", attributes: ["encoding"] },

    "maligngroup": { children: 0,        attributes: ["groupalign"] },

    // tokens
    "malignmark":  { children: 0,        attributes: [] },
    "mi":          { children: "tok",    attributes: ["fontsize", "fontweight", "fontstyle", "fontfamily", "color"] },
    "mn":          { children: "tok",    attributes: ["fontsize", "fontweight", "fontstyle", "fontfamily", "color"] },
    "mtext":       { children: "tok",    attributes: ["fontsize", "fontweight", "fontstyle", "fontfamily", "color"] },
    "ms":          { children: "tok",    attributes: ["fontsize", "fontweight", "fontstyle", "fontfamily", "color",
                                                  "lquote", "rquote"] },
    "mspace":      { children: "tok",    attributes: ["fontsize", "fontweight", "fontstyle", "fontfamily", "color",
                                                  "width", "height", "depth"] },
    "mo":          { children: "tok",    attributes: ["fontsize", "fontweight", "fontstyle", "fontfamily", "color",
                                                  "form", "fence", "separator", "lspace", "rspace", "stretchy", "symmetric",
                                                  "maxsize", "minsize", "largeop", "moveablelimits", "accent"] },

    "mrow":        { children: "normal", attributes: [] },
    "mfrac":       { children: 2,        attributes: ["linethickness"] },
    "msqrt":       { children: "normal", attributes: [] },
    "mroot":       { children: 2,        attributes: [] },
    "mstyle":      { children: "normal", attributes: ["scriptlevel", "displaystyle", "scriptsizemultiplier", "scriptminsize", "color", "background"] },
    "merror":      { children: "normal", attributes: [] },
    "mpadded":     { children: "normal", attributes: ["width", "lspace", "height", "depth"] },
    "mphantom":    { children: "normal", attributes: [] },
    "mfenced":     { children: "normal", attributes: ["open", "close", "separators"] },
    "msub":        { children: 2,        attributes: ["subscriptshift"] },
    "msup":        { children: 2,        attributes: ["superscriptshift"] },
    "msubsup":     { children: 3,        attributes: ["subscriptshift", "superscriptshift"] },
    "munder":      { children: 2,        attributes: ["accentunder"] },
    "mover":       { children: 2,        attributes: ["accent"] },
    "munderover":  { children: 3,        attributes: ["accent", "accentunder"] },
    "mmultiscripts": { children: "ms",   attributes: [] },
    "mtable":      { children: "normal", attributes: ["align", "rowalign", "columnalign", "groupalign", "alignmentscope", "rowspacing", "columnspacing", "rowlines", "columnlines", "frame", "framespacing", "equalrows", "equalcolumns", "displaystyle", "width"] },
    "mtr":         { children: "normal", attributes: ["rowalign", "columnalign", "groupalign"] },
    "mlabeledtr":  { children: "normal", attributes: ["rowalign", "columnalign", "groupalign"] },
    "mtd":         { children: "normal", attributes: ["rowspan", "columnspan", "rowalign", "columnalign", "groupalign"] },

    "emptyset":    { children: 0,        attributes: [] }, // one of the few content tags that has an obvious effect...


    "maction":     { children: "normal", attributes: ["actiontype", "selection"] },

    "menclose":    { children: "normal", attributes: ["notation"] },

    "foo":         { children: "normal", attributes: [] }
  };

  var elements = [];
  for (var tag in elementsX)
    elements[tag] = elementsX[tag].attributes;



  /*

  // XXX resurrect this "make sure things have the right number of children" code

  function createToken(tag, text)
  {
    var e = document.createElementNS("http://www.w3.org/1998/Math/MathML", tag);
    e.appendChild(document.createTextNode(text));
    return e;
  }


  function makeFixMathChildCounts(n, commandnn)
  {
    t = n.tagName;
    var commands = [];

    if (t && elements[t]) {
      desiredChildren = elements[t].children;

      if (desiredChildren == "tok") {
        for(i=n.childNodes.length - 1; i >= 0; --i) {
          c=n.childNodes[i];
          if (c.nodeType != 3) {
            commands.push("11; removeChildAt(" + commandnn + ", " + i + ");");
          }
        }
        if (commands.length)
          return commands;
      }


      if (typeof desiredChildren == "number") {

        currentChildren = n.childNodes.length;


        function isWhitespace(s) { return !/[^\s]/.test(s); }

        // Remove all whitespace nodes. (Why? Wouldn't *counting* the non-whitespace-node children be simpler?)
        for(i = n.childNodes.length - 1; i >= 0; --i) {
          c = n.childNodes[i]
          if (c.nodeType == 3 && isWhitespace(c.data)) {
            commands.push("12; removeChildAt(" + commandnn + ", " + i + ");");
            --currentChildren;
          }
        }
        if (commands.length) {
          return commands;
        }

        if (desiredChildren < currentChildren)
          return "removeChildAt(" + commandnn + ", " + rnd(currentChildren) + ");";

        else if (desiredChildren > currentChildren) {
          var fillGapIndex;
          if (rnd(2) === 1)
            fillGapIndex = findDisconnectedElement(n);
          if (fillGapIndex != undefined)
            return "3; insertAsFirstChild(" + commandnn + ", o[" + fillGapIndex + "]);";
          else
            return "4; insertAsFirstChild(" + commandnn + ", createToken('mi', '" + Random.index(['a','b','c','d','e','f','x','y','z']) + "'));";
        }

      }
    }
  }
  */

  return {
     makeCommand: eaCommandMaker("http://www.w3.org/1998/Math/MathML", elements, attributes, commonAttributes),
     elemHash: elements,
     attrHash: attributes,
     elemList: getKeysFromHash(elements),
     attrList: getKeysFromHash(attributes)
  };
})();

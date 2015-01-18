var fuzzerRandomClasses = (function() {

  /*
    // things that are believed to be parsed strangely (see bug 398038)
    "20 10",
    "20 10em",
    "10 1.2em",
    "10 em",

    // close to nscoord_MAX
    "17895684px",
    "17895694px",
    "17895696px",
    "17895697px",
    "17895698px",
    "17895704px"
  */

  function calcExpr()
  {
    function maybeSpace() { if (rnd(5)) return " "; return ""; }

    switch(rnd(5)) {
      case 0:  return "(" + calcExpr() + ")";
      case 1:  return calcExpr() + maybeSpace() + Random.index(["+", "-", "*", "/", "mod"]) + maybeSpace() + calcExpr();
      default: return Random.pick(fuzzValues.numbersWithUnits);
    }
  }

  function lengths()
  {
    if (rnd(4) === 0)
      return "calc(" + calcExpr() + ")";
    return Random.pick(fuzzValues.numbersWithUnits);
  }

  var numbers = fuzzValues.numbers;
  var heights = [lengths];
  var widths = [lengths, ["-moz-max-content", "-moz-min-content", "-moz-available", "-moz-fit-content"]];

  function borderShorthands()
  {
    return Random.pick(lengths) + " " + Random.index(["solid", "dotted", "hidden", "dashed", "double", "groove", "ridge", "inset", "outset", "none"]) + " " + Random.pick(fuzzValues.colors);
  }

  // http://www.w3.org/TR/2003/CR-css3-text-20030514/#text-shadows
  // http://www.w3.org/TR/2005/WD-css3-background-20050216/#the-box-shadow
  function shadows()
  {
    if (rnd(3) === 0)
      return "none";

    if (rnd(2) === 0)
      return Random.index([
        // Examples from http://www.w3.org/Style/Examples/007/text-shadow
        "0.1em 0.1em #333",
        "0.1em 0.1em 0.05em #333",
        "0.1em 0.1em 0.2em black",
        "0.2em 0.5em 0.1em #600, -0.3em 0.1em 0.1em #060, 0.4em -0.3em 0.1em #006",
        "-1px -1px white, 1px 1px #333",
        "1px 1px white, -1px -1px #333",
        "-1px 0 black, 0 1px black, 1px 0 black, 0 -1px black",
        "0 0 0.2em #8F7",
        "0 0 0.2em #F87, 0 0 0.2em #F87",

        // Example from http://www.w3.org/TR/2005/WD-css3-background-20050216/#the-box-shadow
        "0.2em 0.2em #CCC"
      ]);

    var numShadows = rnd(5) + 1;
    var sh = [];
    var i;
    for (i = 0; i < numShadows; ++i) {
      sh[i] = fuzzValues.numbersWithUnits() + " " + fuzzValues.numbersWithUnits() + " ";
      if (rnd(2))
        sh[i] += fuzzValues.numbersWithUnits() + " "; // optional blur radius
      sh[i] += Random.pick(fuzzValues.colors);
    }

    return sh.join(", ");
  }

  function cssContentValues()
  {
    if (rnd(10) === 0) return "none";
    if (rnd(9) === 0) return "normal";

    var s = cssContentPiece();
    var extraPieces = 1 + rnd(6);
    for (var i = 0; i < extraPieces; ++i)
      s = s + " " + cssContentPiece();
    return s;
  }

  function cssContentPiece()
  {
    switch(rnd(10)) {
      case 0:  return cssCounterUse();
      case 1:  return cssCountersUse();
      case 2:  return Random.index(["open-quote", "close-quote", "no-open-quote", "no-close-quote"]);
      case 3:  return Random.index(["attr(href)", "attr(alt)", "attr(id)"]);
      case 4:  return "url(" + cssLiteralString(fuzzValues.URIs()) + ")";
      default: return cssQuotedStrings();
    }
  }

  function cssQuotedStrings()
  {
    return cssLiteralString(Random.pick(fuzzValues.texts));
  }

  function cssLiteralString(s)
  {
    return ("\"" +
             s.replace(/\r/g, "\\00000d")
              .replace(/\n/g, "\\00000a")
              .replace(/"/g,  "\\\"")
             + "\"");
  }

  function cssCounterUse()
  {
    return "counter(chicken" + optionalCommaListStyleType() + ")";
  }

  function cssCountersUse()
  {
    return "counters(chicken, " + cssQuotedStrings() + optionalCommaListStyleType() + ")";
  }

  function optionalCommaListStyleType()
  {
    if (rnd(3) !== 0)
      return "";
    return ", " + propertyValue("list-style-type");
  }

  function cssURLs() {
    return "url(" + cssLiteralString(fuzzValues.URIs()) + ")";
  }

  var backgroundImages = [
    cssURLs,
    function() { return "-moz-element(#" + Random.pick(fuzzValues.names) + ")"; },
    // http://weblogs.mozillazine.org/roc/archives/2008/07/svg_paint_serve.html
    // http://weblogs.mozillazine.org/roc/archives/2008/07/the_latest_feat.html
    function() { return Random.pick(fuzzValues.nameURLRefs); }
  ];

  function cubicBeziers()
  {
    return "cubic-bezier(" + fuzzValues.numbersZeroOne() + ", " +
                             fuzzValues.numbersZeroOne() + ", " +
                             fuzzValues.numbersZeroOne() + ", " +
                             fuzzValues.numbersZeroOne() + ")";
  }

  function oneOrTwos(a, sep)
  {
    return function() {
      if (rnd(2)) {
        return Random.pick(a);
      } else {
        return Random.pick(a) + sep + Random.pick(a);
      }
    };
  }

  // 1. A custom list.
  // Adv: Can specify how to generate values.
  // Dis: Tedious; incomplete.

  // Based on the CSSGen list, which was in turn based on the Random Styles list.
  // Some things are from http://developer.mozilla.org/en/docs/CSS_Reference:Mozilla_Extensions
  var CSSPropHash = {
    "float": ["left", "right", "none"],
    "clear": ["none", "left", "right", "both"],
    "display": [
      // Basic
      "inline", "block", "inline-block", "inline-table", "list-item",
      // Not supported by Gecko
      "run-in",
      // Table display values
      "table", "table-caption",
      "table-row-group", "table-header-group", "table-footer-group",
      "table-row", "table-cell",
      "table-column", "table-column-group",
      // XUL display values
      "-moz-stack", "-moz-inline-stack", "-moz-deck",
      "-moz-box", "-moz-inline-grid", "-moz-grid", "-moz-box", "-moz-inline-box", "-moz-grid-group", "-moz-grid-line", "-moz-popup", "-moz-groupbox"
    ],
    "visibility": ["visible", "hidden", "collapse"],
    "position": ["static", "relative", "absolute", "fixed", "sticky"],
    "overflow": ["visible", "scroll", "hidden", "-moz-scrollbars-horizontal", "-moz-scrollbars-none", "-moz-scrollbars-vertical", "-moz-hidden-unscrollable"],

    "color": fuzzValues.colors,
    "background": ["transparent", fuzzValues.colors, backgroundImages],
    "background-size":
        [lengths,
         function() { return Random.pick(lengths) + " " + Random.pick(lengths); },
         function() { return "auto"               + " " + Random.pick(lengths); },
         function() { return Random.pick(lengths) + " " + "auto"; },
         "auto auto",
         "auto",
         "cover",
         "contain"
        ],

    "width":      widths,
    "max-width":  widths,
    "min-width":  widths,
    "height":     heights,
    "max-height": heights,
    "min-height": heights,

    "left":       widths,
    "right":      widths,
    "top":        heights,
    "bottom":     heights,

    "content": cssContentValues,
    "quotes": ["none", "'open' 'close'", "'>>' '<<'", "'<1>' '<\/1>' '<2>' '<\/2>'",
               function(){ return cssQuotedStrings() + " " + cssQuotedStrings(); }],
    "counter-reset": ["chicken", "egg", "chicken -1 egg", function() { return "chicken " + fuzzValues.numbers(); }],
    "counter-increment": ["chicken", "egg", "chicken -1 egg", function() { return "chicken " + fuzzValues.numbers(); }],
    "list-style-image": ["none", backgroundImages],
    "border": ["none", borderShorthands],
    "outline": ["none", borderShorthands],
    "outline-offset": lengths,
    "padding": lengths,
    "margin": lengths,
    "opacity": ["0", "0.2", "1", numbers],
    "z-index": ["5", "0", "-200", numbers],

    // Fonts & Text
    "letter-spacing": lengths,
    "word-spacing": lengths,
    "text-align": ["left", "right", "center", "justify", "-moz-left", "-moz-right", "-moz-center", "start", "end"],
    "vertical-align": ["baseline", "sub", "super", "top", "text-top", "middle", "bottom", "text-bottom", lengths],
    "font": function() {
      var features = [];
      // Font-family is weird. The first few sub-properties can be ordered in various ways...
      // https://developer.mozilla.org/en-US/docs/Web/CSS/font
      for (let sub of ["font-style", "font-variant", "font-weight", "font-stretch"]) {
        if (rnd(2)) {
          features.push(propertyValue(sub));
        }
      }
      Random.shuffle(features);
      features.push(propertyValue("font-size") + rnd(2) ? "" : "/" + propertyValue("line-height"));
      features.push(propertyValue("font-family"));
      if (rnd(30) === 0) {
        Random.shuffle(features);
      }
      return features.join(" ");
    },
    "font-size": lengths,
    "font-size-adjust": fuzzValues.numbers,
    "font-family": [
      fuzzValues.fontFaces,
      function() { return cssLiteralString(Random.pick(fuzzValues.fontFaces)); },
      "-moz-use-system-font", // "-moz-use-system-font is the value we use for all the 'font' subproperties to say that 'font' was set to one of the system font values"
      function() { return propertyValue("font-family") + ", " + propertyValue("font-family"); }
    ],
    "-moz-font-feature-settings":
      function() {
        var features = ["liga", "hlig"];
        var r = [];
        if (rnd(3) === 0) {
          // List from http://en.wikipedia.org/wiki/List_of_typographic_features#OpenType_Typographic_Features
          // (http://www.microsoft.com/typography/otspec/featurelist.htm might be a better list)
          // These are defined per-font; they have no special meaning to the font engine.
          features = ["aalt", "nalt", "afrc", "c2pc", "c2sc", "case+cpsp", "calt", "clig", "cswh", "dnom", "dlig", "expt", "frac", "fwid", "ccmp", "half", "hist", "hlig", "hojo", "js04", "js78", "js83", "js90", "jalt", "locl", "mark", "mkmk", "mgrk", "nlck", "numr", "ordn", "ornm", "pcap", "pnum+lnum", "pnum+onum", "pwid", "qwid", "rlig", "ruby", "sinf", "smpl", "zero", "smcp", "liga", "salt", "ss01", "ss02", "ss03", "subs", "sups", "swsh", "tnum+lnum", "tnum+onum", "twid", "titl", "trad", "tnam", "unic"];
        }
        for (var i = 0; i < features.length; ++i) {
          if (rnd(2))
            r.push(features[i] + "=" + rnd(2));
        }

        r = '"' + r.join(",") + '"';
        dumpln(r);
        return r;
      },

    "text-overflow": oneOrTwos(["clip", "ellipsis", cssQuotedStrings], " "),
    "text-shadow": shadows,
    "box-shadow": shadows,
    "text-indent": widths,

    // http://developer.mozilla.org/en/docs/CSS:-moz-appearance
    // http://mxr.mozilla.org/mozilla-central/source/layout/style/nsCSSProps.cpp#477
    "-moz-appearance": ["none", "button", "radio", "checkbox", "button-bevel", "toolbox", "toolbar", "toolbarbutton", "toolbargripper", "dualbutton", "toolbarbutton-dropdown", "button-arrow-up", "button-arrow-down", "button-arrow-next", "button-arrow-previous", "meterbar", "meterchunk", "separator", "splitter", "statusbar", "statusbarpanel", "resizerpanel", "resizer", "listbox", "listitem", "treeview", "treeitem", "treetwisty", "treetwistyopen", "treeline", "treeheader", "treeheadercell", "treeheadersortarrow", "progressbar", "progresschunk", "progressbar-vertical", "progresschunk-vertical", "tab", "tabpanels", "tabpanel", "tab-scroll-arrow-back", "tab-scroll-arrow-forward", "tooltip", "spinner", "spinner-upbutton", "spinner-downbutton", "spinner-textfield", "scrollbar", "scrollbar-small", "scrollbarbutton-up", "scrollbarbutton-down", "scrollbarbutton-left", "scrollbarbutton-right", "scrollbartrack-horizontal", "scrollbartrack-vertical", "scrollbarthumb-horizontal", "scrollbarthumb-vertical", "textfield", "textfield-multiline", "caret", "searchfield", "menulist", "menulist-button", "menulist-text", "menulist-textfield", "scale-horizontal", "scale-vertical", "scalethumb-horizontal", "scalethumb-vertical", "scalethumbstart", "scalethumbend", "scalethumbtick", "groupbox", "checkbox-container", "radio-container", "checkbox-label", "radio-label", "button-focus", "window", "dialog", "menubar", "menupopup", "menuitem", "checkmenuitem", "radiomenuitem", "menucheckbox", "menuradio", "menuseparator", "menuarrow", "menuimage", "menuitemtext", "-moz-win-media-toolbox", "-moz-win-communications-toolbox", "-moz-win-browsertabbar-toolbox", "-moz-win-glass", "-moz-win-borderless-glass", "-moz-mac-unified-toolbar", "-moz-window-titlebar", "-moz-window-titlebar-maximized", "-moz-window-frame-left", "-moz-window-frame-right", "-moz-window-frame-bottom", "-moz-window-button-close", "-moz-window-button-minimize", "-moz-window-button-maximize", "-moz-window-button-restore", "-moz-window-button-box", "-moz-window-button-box-maximized", "-moz-win-exclude-glass"],

    // A few SVG style properties (now supported through CSS!)
    // The rendering aspect is fuzzed better by fuzzerSVGAttributes, but good to fuzz the CSS aspect too.
    "fill-opacity": ["0", ".1", "1", numbers],

    // A few SVG-referencing properties are supported in HTML now!
    // http://weblogs.mozillazine.org/roc/archives/2008/06/applying_svg_ef.html
    "mask":      [cssURLs, fuzzValues.nameURLRefs, function() { return Random.pick(fuzzerSVGAttributes.maskRefs); }],
    "clip-path": [cssURLs, fuzzValues.nameURLRefs, function() { return Random.pick(fuzzerSVGAttributes.clipPathRefs); }],
    "filter":    [cssURLs, fuzzValues.nameURLRefs, function() { return Random.pick(fuzzerSVGAttributes.filterRefs); }],

    // -moz-column tends to be buggy
    "-moz-column-count": ["-1", "0", "1", "2", "3", "15", numbers],
    "-moz-column-width": ["1px", "auto", lengths],
    "-moz-column-gap": ["1px", "auto", lengths],
    "-moz-column-rule": borderShorthands,

    // https://developer.mozilla.org/en/CSS/CSS_animations
    // Many of these properties have a mysterious kleene star. Multiple animations on a single element, I guess?
    "animation-duration": fuzzValues.durations,
    "animation-name": fuzzValues.names, // must match a moz-keyframes css declaration to be interesting
    "animation-timing-function": ["ease", "linear", "ease-in", "ease-out", "ease-in-out", cubicBeziers],

    // flex
    "order": ["0", "1", "2", "3", "4", numbers],

    "-moz-control-character-visibility": ["visible", "hidden"],
  };

  // 2. Extract information from property_database.js.
  // Adv: Contains full lists of values for many enumerated properties.
  // Dis: Does not describe how to generate new values. (Mitigated by tricks in randomDeclaration.)
  // Dis: Intended to test the style system only, so some properties (notably display, moz-appearance, text-align) have incomplete lists.
  // Dis: Gecko only (and requires a source tree).
  function importPropertyDatabase()
  {
    var pd;
    try {
      var pdScript = fuzzPriv.cssPropertyDatabase();

      var pdFunc = new Function(
        "var SpecialPowers = { getBoolPref: function(p) { return true; } };" +
        pdScript +
        "return gCSSProperties;"
      );

      pd = pdFunc();

      // Sanity check
      void (pd["float"].other_values[0]);
    } catch(e) {
      dumpln("Error importing the CSS property database: " + e);
      return false;
    }

    for (var p in pd) {
      var v = pd[p].initial_values.slice(0);
      v = v.concat(pd[p].other_values);
      if ("invalid_values" in pd[p]) {
        v = v.concat(pd[p].invalid_values);
      }
      if ("quirks_values" in pd[p]) {
        v = v.concat(Object.keys(pd[p].quirks_values));
      }
      if (!(p in CSSPropHash)) {
        //dumpln("Adding from property_database.js: " + p);
        CSSPropHash[p] = v;
      } else {
        //dumpln("Merging from property_database.js: " + p);
        // Equal chance of picking from our values or from property_database.js's values
        // (even if one of the lists is longer)
        CSSPropHash[p] = [CSSPropHash[p], v];
      }
    }
  }
  importPropertyDatabase();

  function importProperties(style, note)
  {
    var len = style.length;
    for (var i = 0; i < len; ++i) {
      var prop = style.item(i);
      if (!(prop in CSSPropHash)) {
        //dumpln("Adding from " + note + ": " + prop);
        CSSPropHash[prop] = randomCSSValue;
      }
    }
  }

  // 3. Get a list from getComputedStyles.
  // Adv: Large list; almost exhaustive.
  // Dis: Missing "input properties" (?) such as -moz-margin-start.
  // Dis: No information about values.
  var v = document.createElementNS("http://www.w3.org/1999/xhtml", "div");
  if (window.getComputedStyle) {
    importProperties(window.getComputedStyle(v, null), "computed style");
  }

  var CSSPropList = getKeysFromHash(CSSPropHash);

  function randomCSSValue() {
    return rnd(2) ?
      Random.index(["", "inherit", "initial", "unset", "auto"]) :
      Random.pick(CSSPropHash[Random.index(CSSPropList)]);
  }

  // Concentrate on a set of related properties.
  // Weight toward properties whose name contains this string.  ('basics' and 'flex' are special.)
  var hammer = "basics";

  function chooseHammer()
  {
    switch(rnd(10)) {
      case 0:  return "basics";
      case 1:  return "flex";
      default:
        var p = Random.index(CSSPropList);
        if (p.substr(0, 5) == "-moz-")
          p = p.slice(5);
        return Random.index(p.split("-"));
    }
  }

  function setHammer(h) { hammer = "" + h; }

  function propertyValue(prop) {
    return rnd(10) ? Random.pick(CSSPropHash[prop]) : randomCSSValue();
  }

  function randomProperty()
  {
    if (rnd(2) === 0) {
      if (hammer == "basics") {
        return Random.index(["display", "float", "visibility", "position", "overflow", "content"]);
      }
      if (hammer == "flex") {
        return Random.index(["display", "align-items", "align-self", "flex", "flex-basis", "flex-direction", "flex-grow", "flex-shrink", "order", "justify-content"]);
      }
      return Random.index(CSSPropList.filter(function(p) { return p.indexOf(hammer) != -1; }));
    }

    return Random.index(CSSPropList);
  }

  function randomDeclaration()
  {
    var prop = randomProperty();
    var value = propertyValue(prop);

    if (typeof value == "number")
      value = "" + value;

    if (rnd(10) === 0) {
      // Append another value for the same property
      value = value + Random.index(["", " ", ", "]) + propertyValue(prop);
    }

    if (typeof value != "string") {
      dumpln("FAILURE: " + prop + " -> " + value);
    }

    if (rnd(2) === 0)
      value = fuzzValues.modifyNumbersInString(value);

    if (rnd(50) === 0)
      value = fuzzValues.modifyText(value);

    return { prop: prop, value: value };
  }


  var classes = [ "cat", "toad", "zebra", "lizard", "penguin", "elephant" ];

  var importances = ["", "", "", "", "", "", "", "", "", "", "!important", " ! important"];



  function randomSelector()
  {
    var selector;

    // Slightly more evil than fuzzerRandomClasses wants.
    if (rnd(10) === 0)
      return Random.pick(fuzzValues.cssSelectors);

    if (rnd(30) === 0) {
      selector = "*";
    } else {
      selector = "." + Random.index(classes);
    }

    while (rnd(3) === 0)
      selector += Random.pick(fuzzValues.cssPseudoClasses);

    if (rnd(3) === 0)
      selector += Random.pick(fuzzValues.cssPseudoElements);

    return selector;
  }


  function randomRule()
  {
    var importance;
    var rule = randomSelector() + " { ";
    var numProps = rnd(10);

    for (var i = 0; i < numProps; ++i) {
      var decl = randomDeclaration();
      importance = Random.index(importances);
      rule += decl.prop + ": " + decl.value + importance + "; ";
    }

    rule += "}";
    return rule;
  }

  function randomStatement()
  {
    switch(rnd(20)) {
    case 0:  return randomStatement() + " " + randomStatement();
    case 1:  return randomCSSAnimation();
    case 2:  return '@import ' + cssLiteralString(fuzzTextDataURI("text/css", randomStatement()));
    case 3:  return "@namespace html url(http://www.w3.org/1999/xhtml); " + randomStatement();
    case 4:  return "@supports (color: blue) { " + randomStatement() + " }";
    case 5:  return "@supports (color: quux) { " + randomStatement() + " }";
    case 6:  return "@media all { " + randomStatement() + " }";
    case 7:  return "@media not all { " + randomStatement() + " }";
    case 8:  return randomFontFaceRule();
    case 9:  return '@charset "UTF-8";';
    default: return randomRule();
    }
  }

  function randomFontFaceRule()
  {
    var s = "@font-face { ";
    s += "font-family: '" + Random.pick(fuzzValues.fontFaces) + "'; ";
    if (rnd(2)) {
      s += "src: url('" + fuzzSrcTreePathToURI(Random.pick(fuzzValues.srcTreeFontFilenames)) + "'); ";
    } else {
      s += "src: local('" + Random.pick(fuzzValues.fontFaces) + "'); ";
    }
    s += "}";
    return s;
  }

  function randomCSSAnimation()
  {
    var animName = Random.pick(fuzzValues.names);
    var s = "@keyframes " + animName + " { ";

    for (var j = 0; j < 3; ++j) {
      s += randomKeyframePoints();
      s += " { ";
      for (var i = 0; i < 3; ++i) {
        var decl = randomDeclaration();
        // no !important inside animations
        s += decl.prop + ": " + decl.value + "; ";
      }
      s += "} ";
    }

    s += "} ";

    if (rnd(4)) {
      var duration = Random.pick(fuzzValues.durations);
      s += randomSelector() + " { animation-name: " + animName + "; animation-duration: " + duration + "; }";
    }

    return s;
  }

  function randomKeyframePoints()
  {
    return Random.index(["from", "to", "0%", "20%", "40%", "60%", "80%", "100%", "20%, 50%"]);
  }


  function makeCommand()
  {
    if (rnd(100) === 0)
      return "fuzzerRandomClasses.setHammer(" + simpleSource(chooseHammer()) + ");";

    switch(rnd(2)) {
      case 0:
        // Pick a slot.  If there's a stylesheet there, remove it.  Otherwise, add one there.
        var slot = rnd(20);
        if (sheetNodes[slot]) {
          return "fuzzerRandomClasses.removeSheet(" + slot + ");";
        } else {
          var cssText = randomStatement();
          var holder = (rnd(5) ? "null" : Things.instance("Element"));
          var scoped = (rnd(300) === 0); // infrequent: bug 926717
          return "fuzzerRandomClasses.addSheet(" + slot + ", " + simpleSource(cssText) + ", " + holder + ", " + scoped + ");";
        }

      default:
        // Change a random element's class.
        return Things.instance("Element") +".setAttribute(\"class\", " + simpleSource(Random.index(classes)) + ");";
    }
  }


  var sheetNodes = []; // [0..19] --> (node | null)

  function addSheet(slot, text, sheetHolder, scoped)
  {
    sheetHolder = sheetHolder || document.getElementsByTagName("head")[0] || document.documentElement;

    var sheet = document.createElementNS("http://www.w3.org/1999/xhtml", "style");
    sheet.appendChild(document.createTextNode(text));
    sheet.style.display = "none";
    if (scoped) sheet.scoped = true;
    sheetHolder.appendChild(sheet);

    sheetNodes[slot] = sheet;
  }

  function removeSheet(slot)
  {
    var sheet = sheetNodes[slot];
    sheetNodes[slot] = null;

    sheet.parentNode.removeChild(sheet);
  }

  return {
    makeCommand: makeCommand,
    addSheet: addSheet,                      // Random Classes callback
    removeSheet: removeSheet,                // Random Classes callback
    setHammer: setHammer,                    // Random Classes callback
    randomDeclaration: randomDeclaration,    // Used by fuzzerRandomStyles
    randomRule: randomRule,                  // Used by fuzzerDOMCSS
    randomProperty: randomProperty,          // Used by fuzzerDOMStyle
    propertyValue: propertyValue,            // Used by fuzzerCanvas
  };
})();

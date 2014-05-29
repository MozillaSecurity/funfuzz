var fuzzerHTMLAttributes = (function() {

  function spaceSepSubset(a)
  {
    var subset = [];
    for (var i = 0; i < a.length; ++i) {
      if (rnd(2)) {
        subset.push(a[i]);
      }
    }
    // Wouldn't hurt to sometimes shuffle, repeat, include bogus things, etc.
    // And weight toward all or none
    return subset.join(" ");
  }

  // Attribute values (specific to HTML)
  var relations = ["alternate", "stylesheet", "icon", "prefetch", "next", "prev", "search", "import"];
  var listOfFrameSizes = ["100,*", "*,100", "100,100,100,100,100", "*", "30%,20%,50%", "100%,*"];

  var commonAttributes = ["id", "name", "width", "height", "lang", "spellcheck", "dir", "hidden"];

  var attributes = {
    "randomness": fuzzTotallyRandomValue,
    "id": fuzzValues.names,
    "name": fuzzValues.names,
    "for": fuzzValues.names, // does not use #.  what about <script for> -- is that different? <output for> actually takes a space-separated list of names.
    "usemap": fuzzValues.namerefs, // uses #
    "href": [fuzzValues.namerefs, fuzzValues.URIs],
    "type": [
      // <link> elements
      fuzzValues.mimeTypes,
      // http://www.whatwg.org/specs/web-apps/current-work/multipage/the-input-element.html
      ["hidden", "text", "search", "tel", "url", "email", "password", "datetime", "date", "month", "week", "time", "datetime-local", "number", "range", "color", "checkbox", "radio", "file", "submit", "image", "reset", "button"],
      // list types in HTML 3.2 (HTML5 doesn't include these, preferring CSS)
      ["i","1","A","I","a"]
    ],
    "enctype": fuzzValues.formEncTypes,
    "formenctype": fuzzValues.formEncTypes,
    "accept": fuzzValues.mimeTypes,
    "accept-charset": fuzzValues.charsets,
    "charset": fuzzValues.charsets,
    "action": fuzzValues.URIs,
    "formaction": fuzzValues.URIs,
    "method": ["GET", "POST"],
    "maxlength": fuzzValues.numbers,
    "placeholder": fuzzValues.texts,
    "tabindex": fuzzValues.numbers,
    "width": [fuzzValues.numbers, fuzzValues.numbersWithUnits],
    "height": [fuzzValues.numbers, fuzzValues.numbersWithUnits],
    "dir": ["ltr", "rtl", "auto"],
    "checked": "checked",
    "disabled": "disabled",
    "readonly": "readonly",
    "indeterminate": "indeterminate",
    "autofocus": "autofocus",
    "autocomplete": "autocomplete",
    "novalidate": "novalidate",
    "formnovalidate": "formnovalidate",
    "required": "required",
    "size": [["1", "2", "3", "4", "5", "6", "7"], fuzzValues.numbers],
    "src": fuzzValues.URIs,
    "data": fuzzValues.URIs,
    "crossorigin": ["", "anonymous", "use-credentials"],
    "alt": fuzzValues.texts,
    "ismap": "ismap", // ?
    "accesskey": fuzzValues.chars,
    "multiple": "multiple", // ?
    "selected": "selected",
    "label": fuzzValues.texts,
    "target": ["_blank", ""],
    "pattern": ["[0-9][A-Z]{3}", "[0-9]+"],
    "step": fuzzValues.numbers,
    "list": fuzzValues.names,

    // <input> of various types
    "value": [fuzzValues.numbers, "#ffffff"],

    // progress, meter
    "min": fuzzValues.numbers,
    "max": fuzzValues.numbers,
    "low": fuzzValues.numbers,
    "high": fuzzValues.numbers,
    "optimum": fuzzValues.numbers,
    "form": fuzzValues.names,
    "labels": fuzzValues.names, // should be multiples?

    // keygen
    "keytype": ["rsa", "dsa"],
    "challenge": "mychallenge",

    "rows": [fuzzValues.numbers, listOfFrameSizes], // listOfFrameSizes is for "frameset", while numbers is for "textarea".
    "cols": [fuzzValues.numbers, listOfFrameSizes],
    "rel": relations,
    "rev": relations,

    // Image maps
    "shape": "rect",
    "coords": "5,10,15,20",
    "nohref": "nohref", // ?

    "longdesc": fuzzValues.URIs,

    "pluginspage": fuzzValues.URIs,
    "pluginsurl": fuzzValues.URIs,
    "hidden": fuzzValues.booleans,
    "autostart": fuzzValues.booleans,

    "cite": fuzzValues.URIs,
    "datetime": ["2006-06-04", "2001-05-15 19:00"], // ?

    // meta
    "http-equiv": ["content-language", "content-type", "default-style", "refresh", "set-cookie"],
    "content": [
      fuzzValues.languages,
      function() { return "text/html; " + Random.pick(fuzzValues.charsets); },
      fuzzValues.names, // ...
      fuzzValues.metaRefreshContent,
      "foo=bar", // ...
    ],

    "media": ["all"], // CSS media query
    "scoped": "scoped",
    "defer": "defer",
    "async": "async",
    "event": [],

    "align": ["left", "center", "right", "justify", ":", // HTML 4 for tables (colon is for "char" in the HTML 4 spec (?))
              "top", "middle", "bottom", "left", "right" ], // HTML 3.2 for images

    "vspace": fuzzValues.numbers,
    "hspace": fuzzValues.numbers,

    "bgcolor": fuzzValues.colors,
    "text": fuzzValues.colors,
    "link": fuzzValues.colors,
    "vlink": fuzzValues.colors,
    "alink": fuzzValues.colors,

    "color": fuzzValues.colors,
    "face": fuzzValues.fontFaces,

    "background": fuzzValues.URIs,

    "noshade": "noshade", // ?

    "valign": ["top", "middle", "bottom", "baseline"],
    "border": fuzzValues.numbers,
    "cellspacing": fuzzValues.numbers,
    "cellpadding": fuzzValues.numbers,
    "summary": fuzzValues.texts,
    "span": fuzzValues.tableSpans,
    "rowspan": fuzzValues.tableSpans,
    "colspan": fuzzValues.tableSpans,
    "scope": ["row", "col", "rowgroup", "colgroup"],
    "headers": fuzzValues.names, // really multiple names
    "axis": fuzzValues.names, // ?

    // Obscure stuff from the TABLES section of http://www.w3.org/TR/REC-html40/sgml/dtd.html
    "frame": ["void", "above", "below", "hsides", "lhs", "rhs", "vsides", "box", "border"],
    "rules": ["none", "groups", "rows", "cols", "all"],

    // marquee
    "behavior": ["scroll", "slide", "alternate"],
    "direction": ["left", "right", "down", "up"],
    "loop": [-1, 0, 1, 2, fuzzValues.numbers, "true"], // also a boolean attribute on media elements
    "scrollamount": fuzzValues.numbers,
    "scrolldelay": fuzzValues.numbers,
    "truespeed": fuzzValues.numbers,

    // frameset
    "frameborder": [0, 1],
    "marginwidth": fuzzValues.numbers,
    "marginheight": fuzzValues.numbers,
    "noresize": ["noresize"],
    "scrolling": ["yes", "no", "auto"],

    // frames
    "mozbrowser": ["true"],
    "allowfullscreen": ["true"],
    "sandbox": function() { return spaceSepSubset(["allow-forms", "allow-pointer-lock", "allow-popups", "allow-same-origin", "allow-scripts", "allow-top-navigation"]); },
    "seamless": ["true"],
    "srcdoc": fuzzValues.htmlMarkup,

    // embed
    "allowscriptaccess": ["always"],

    // applet
    "code": ["Spampede.class"],
    "codebase": ["http://www.squarefree.com/spampede/", "https://www.squarefree.com/spampede/", fuzzValues.URIs],
    "object": [fuzzValues.URIs],

    // video and audio
    "autoplay": ["autoplay"],
    "controls": ["controls"],
    "playcount": fuzzValues.numbers,
    "poster": fuzzValues.URIs,

    "lang": fuzzValues.languages,
    "hreflang": fuzzValues.languages,

    "reversed": ["reversed"],
    "spellcheck": ["true", "false"],
  };


  var elements =
  {
    "tt": [],
    "i": [],
    "b": [],
    "big": [],
    "small": [],
    "em": [],
    "strong": [],
    "dfn": [],
    "code": [],
    "samp": [],
    "kbd": [],
    "var": [],
    "cite": [],
    "abbr": [],
    "acronym": [],
    "br": [],
    "q": ["cite"],
    "sub": [],
    "sup": [],
    "span": [],
    "bdo": ["dir"], // but everything can have dir, but it's required for bdo

    "form": ["action", "method", "enctype", "accept", "name", "accept-charset", "target", "novalidate"],

    "input": ["type", "name", "value", "checked", "disabled", "readonly", "size", "maxlength", "src", "alt", "usemap", "ismap", "tabindex", "accesskey", "accept", "indeterminate", "autofocus", "placeholder", "required", "formaction", "formtarget", "formnovalidate", "formenctype", "autocomplete", "height", "list", "max", "min", "multiple", "pattern", "step"],
    "output": ["for", "form", "name"],
    "select": ["name", "size", "multiple", "disabled", "readonly", "tabindex"],
    "option": ["selected", "disabled", "label", "value"],
    "optgroup": ["label", "disabled"],
    "textarea": ["name", "rows", "cols", "disabled", "readonly", "tabindex", "accesskey", "spellcheck"],
    "button": ["name", "value", "type", "disabled", "tabindex", "accesskey", "formaction", "formtarget"],
    "label": ["for", "accesskey"],
    "meter": ["value", "min", "max", "low", "high", "optimum", "form", "labels"],
    "progress": ["value", "max", "form"],
    "datalist": [],

    "h2": [],
    "ol": ["reversed"],
    "ul": [],
    "li": [],
    "dl": [],
    "dd": [],
    "dt": [],
    "pre": ["width"], // width only in HTML 3.2
    "link": ["charset", "href", "hreflang", "type", "rel", "rev", "media"],
    "noscript": [],
    "blockquote": [],
    "div": [],
    "p": [],
    "hr": ["align", "noshade", "size", "width"],
    "fieldset": [],
    "legend": ["accesskey"],
    "a": ["name", "href", "accesskey", "rel", "rev", "shape", "coords", "tabindex"],
    "map": ["name"],
    "area": ["nohref", "shape", "coords", "href", "alt", "tabindex", "accesskey"],
    "img": ["src", "alt", "longdesc", "name", "height", "width", "usemap", "ismap", "hspace", "vspace", "align", "crossorigin"], // some attributes only in HTML 3.2
    "applet": ["codebase", "code", "object", "archive", "align", "alt", "height", "width", "hspace", "vspace", "name"], // http://docs.oracle.com/javase/1.4.2/docs/guide/misc/applet.html
    "object": ["declare", "classid", "codebase", "data", "type", "codetype", "archive", "standby", "height", "width", "usermap", "name", "tabindex", "data"],
    "embed": ["src", "type", "pluginspage", "pluginsurl", "hidden", "width", "height", "autostart", "allowfullscreen", "allowscriptaccess"],
      // <embed> is not in the DTD??
    "param": ["id", "name", "value", "valuetype", "type"],
    "ins": ["cite", "datetime"],
    "del": ["cite", "datetime"],

    "table": ["summary", "width", "border", "frame", "rules", "cellspacing", "cellpadding"],
    "caption": [],
    "colgroup": ["span", "width", "align", "valign"],
    "col": ["span", "width", "align", "valign"],
    "thead": ["align", "valign"],
    "tr": ["align", "valign"],
    "td": ["align", "valign", "abbr", "axis", "headers", "scope", "rowspan", "colspan"],
    "th": ["align", "valign", "abbr", "axis", "headers", "scope", "rowspan", "colspan"],

    "base": ["href", "target"],
    "meta": ["http-equiv", "content", "name", "scheme", "charset"],
    "style": ["type", "media", "title", "scoped"],
    "script": ["charset", "type", "src", "defer", "async", "event", "for"],
    "html": [],
    "head": [],
    "body": ["bgcolor", "text", "link", "vlink", "alink", "background"], // attributes only in HTML 3.2
    "title": [],

    // evil, probably not in HTML 4 DTD for a good reason
    "xmp": [],
    "listing": [],
    "plaintext": [],

    "isindex": [], // obsolete

    // From HTML 3.2 only:
    "s": [],
    "basefont": ["size", "color", "face"],
    "font": ["size", "color", "face"],
    "menu": [], // ???

    // Everyone loves to hate...
    "blink": [],
    "marquee": ["behavior", "bgcolor", "direction", "height", "hspace", "loop", "scrollamount", "scrolldelay", "truespeed", "vspace", "width"],

    // New things
    "canvas": ["width", "height"],

    // http://lxr.mozilla.org/mozilla-central/source/editor/libeditor/html/nsHTMLEditUtils.cpp#585 -- i don't know what some of these are!
    "dir": [],
    "keygen": ["keytype", "challenge", "autofocus", "disabled", "form", "name"],
    "nobr": [],
    "multicol": [],
    "u": [],
    "wbr": [],
    "spacer": [],
    "noframes": [],
    "noembed": [],

    // don't forget the lonely "unknown element"!
    "foo": [],

    "iframe": ["longdesc", "name", "src", "srcdoc", "frameborder", "marginwidth", "marginheight", "scrolling", "align", "width", "height", "mozbrowser", "allowfullscreen", "sandbox", "seamless"],
    "frame": ["name", "src", "frameborder", "marginwidth", "marginheight", "noresize", "scrolling"],
    "frameset": ["rows", "cols"],

    "video": ["autoplay", "controls", "end", "height", "loopend", "loopstart", "playcount", "poster", "src", "start", "width"],
    "audio": ["autoplay", "controls", "end", "loopend", "loopstart", "playcount", "src", "start"],
    "track": [],

    // "Section" elements, many of which are new in HTML5
    "article": [],
    "aside": [],
    "footer": [],
    "header": [],
    "nav": [],
    "section": [],
    "hgroup": [],
    "address": [],

    // New "grouping content" elements in HTML
    "figure": [],
    "figcaption": [],

    // New "text-level semantics" elements in HTML5
    "time": ["datetime"],
    "data": ["value"],
    "mark": [],
    "ruby": [],
    "rt": [],
    "rb": [],
    "bdi": ["dir"],

    // Shadow DOM
    "content": [], // ???
    "shadow": [], // ???
    "template": [], // ???
  };


  return {
           makeCommand: eaCommandMaker("http://www.w3.org/1999/xhtml", elements, attributes, commonAttributes),
           elemHash: elements,
           attrHash: attributes,
           elemList: getKeysFromHash(elements),
           attrList: getKeysFromHash(attributes)
         };
})();

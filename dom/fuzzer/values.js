// domInteresting.py will watch for 'nsXPCComponents_Classes' in stdout.
// This string should not contain quote characters.
var escalationAttempt = "dump(Components.classes+String.fromCharCode(10));";

var fuzzValues = {

  booleans: ["true", "false"],
  colors: ["lime", "red", "blue", "#CCC", "#888888", "transparent", "rgba(50,50,255,0.8)", "-moz-use-text-color", "-moz-nativehyperlinktext", "invert", "WindowText", "ThreeDHighlight", "-moz-default-background-color", "-moz-default-color", "currentColor"],

  unsignedNumbers: function() {
    var v;
    if (rnd(100) === 0) {
      // Return a string meant to test the limits of string-to-float parsers
      switch (rnd(8)) {
        // Obscure behaviors of strtod (dtoa.c)
        case 0:  return "0xff";
        case 1:  return "INF";
        case 2:  return "INFINITY";
        case 3:  return "NAN";
        // Even more obscure behaviors of strtod (see https://bugzilla.mozilla.org/show_bug.cgi?id=584252)
        case 4:  return "NAN(fffffffffffff)";
        case 5:  return "NAN(ffffeeeeeff0f)";
        // Exponential notation
        // (Note: max for double is about 1.7*10^308)
        case 6:  return "1e" + (rnd(801) - 400);
        // A number long enough to become Infinity when parsed most float-parsers
        default: return "999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999";
      }
    } else if (rnd(4) === 0) {
      // Make a power of two, plus or minus one.
      // Go beyond 2^32, since there have been bugs involving 2^59 or so!
      v = Math.pow(2, rnd(65)) + rnd(3) - 1;
    } else {
      // Make numbers from 1 to [very huge], weighted toward smaller numbers.
      v = Math.pow(2, rnd.rndReal() * rnd.rndReal() * 65);
      // With plenty of integers and half-integers
      if (rnd(2) === 0) {
        v = Math.floor(v);
        while (rnd(2) === 0) {
          v = v / 2;
        }
      }
      // And some inverses of those numbers.
      if (rnd(6) === 0) {
        v = 1 / v;
      }
    }
    return "" + v;
  },

  numbers: function() {
    var v = fuzzValues.unsignedNumbers();
    return rnd(4) ? v : "-" + v;
  },

  numbersZeroOne: function() {
    switch(rnd(20)) {
    case 0:  return 0;
    case 1:  return 1;
    case 2:  return randomThing(fuzzValues.numbers);
    default: return rnd(100000) / 100000;
    }
  },

  twoNumbers: function() {
    return fuzzValues.numbers() + " " + fuzzValues.numbers();
  },

  jsNumbers: function() {
    switch(rnd(20)) {
    // Special float values
    case 0:  return "(1/0)"; // Infinity
    case 1:  return "(-1/0)"; // -Infinity
    case 2:  return "(0/0)"; // NaN
    case 3:  return "0";
    case 4:  return "(-0)";
    default: return "" + randomThing(fuzzValues.numbers);
    }
  },

  tableSpans: function()
  {
    // http://mxr.mozilla.org/mozilla-central/source/layout/tables/celldata.h#17
    switch(rnd(8)) {
      case 0:  return fuzzValues.numbers();
      case 1:  return "" + (65536 - rnd(6));
      case 2:  return "" + (1000 - rnd(4));
      case 3:  return "" + (rnd(65536));
      default: return "" + rnd(4);
    }
  },

  percents: function() { return (randomThing(fuzzValues.numbers) * 100) + "%"; },
  numbersWithUnits: function () { return randomThing(fuzzValues.numbers) + randomThing(fuzzValues.units); },
  units: ["%", "", ["px", "em", "rem", "ch", "pt", "in", "cm", "pc", "mm", "mozmm", "deg", "grad", "rad", "turn", "vw", "vh", "vmax", "vmin", "s", "ms"]],

  durations: function() {
    // Mostly, use time scales close to fuzzer pauses
    if (rnd(10)) {
      var ms = Math.floor(Math.pow(2, rnd.rndReal() * 14)) - 1;
      return ms + "ms";
    } else {
      return randomThing(fuzzValues.numbers) + rndElt(["ms", "s"]);
    }
  },

  fontFaces: [
    (function randomFontFace() {
      var allFonts;
      return function randomFontFaceInner() {
        if (!allFonts)
          allFonts = (typeof fuzzPriv == "object" && typeof fuzzPriv.fontList == "function") ? fuzzPriv.fontList().split("\n") : ["monospace"];
        return rndElt(allFonts);
      };
    })(),
    [
      // Font families that include multiple fonts
      "monospace",
      "serif",
      "sans-serif",
      "cursive",
      "fantasy",
      "-moz-fixed"
    ],
    [
      // Common and/or interesting fonts
      "Arial",
      "Arial Black", // special: see bug 635640
      "Hei", // chinese
      "Copperplate",
      "Monaco",
      "Marker felt",
      "Papyrus",
      "AppleGothic",
      "Optima",
      "Comic Sans MS",
      "Courier",
      "Symbol",
      "Zapf Dingbats",
      "Zapfino",
      "Roman", // a stroke-based font. see bug 744480.
      // from layout/mathml/mathfont.properties
      "STIXNonUnicode",
      "STIXSizeOneSym",
      "STIXSize1",
      "Asana Math",
      "Standard Symbols L",
      // from modules/libpref/src/init/all.js, font.mathfont-family
      "DejaVu Sans",
      "Cambria Math",
      "Apple Color Emoji",
    ]
  ],

  languages: [
     ["tr", "az"], // special casing for i, I, dotted/dotless variants
     ["nl", "gr"], // special casing rules: https://developer.mozilla.org/en/CSS/text-transform
     ["ja", "zh"], // special justification rules
     ["ar", "he"], // tend to be RTL
     // http://mxr.mozilla.org/mozilla-central/source/gfx/thebes/gfxAtomList.h
     ["en", "x-unicode", "x-western", "ja", "ko", "zh-cn", "zh-hk", "zh-tw", "x-cyrillic", "el", "tr", "he", "ar", "x-baltic", "th", "x-devanagari", "x-tamil", "x-armn", "x-beng", "x-cans", "x-ethi", "x-geor", "x-gujr", "x-guru", "x-khmr", "x-knda", "x-mlym", "x-orya", "x-sinh", "x-telu", "x-tibt", "ko-xxx", "x-central-euro", "x-symbol", "x-user-def", "az", "ba", "crh", "tt"],
     // Seen in mxr
     ["en-US", "fr", "fra", "de", "ru", "en-us", "is-IS", "xyzzy"]
     // http://en.wikipedia.org/wiki/List_of_ISO_639-1_codes ?
  ],

  // http://mxr.mozilla.org/mozilla-central/source/intl/uconv/src/nsUConvModule.cpp#272
  charsets: ["UTF-8", ["ISO-8859-1", "windows-1252", "x-mac-roman", "UTF-8", "us-ascii", "ISO-8859-2", "ISO-8859-3", "ISO-8859-4", "ISO-8859-5", "ISO-8859-6", "ISO-8859-6-I", "ISO-8859-6-E", "ISO-8859-7", "ISO-8859-8", "ISO-8859-8-I", "ISO-8859-8-E", "ISO-8859-9", "ISO-8859-10", "ISO-8859-13", "ISO-8859-14", "ISO-8859-15", "ISO-8859-16", "ISO-IR-111", "windows-1250", "windows-1251", "windows-1253", "windows-1254", "windows-1255", "windows-1256", "windows-1257", "windows-1258", "TIS-620", "windows-874", "ISO-8859-11", "IBM866", "KOI8-R", "KOI8-U", "x-mac-ce", "x-mac-greek", "x-mac-turkish", "x-mac-croatian", "x-mac-romanian", "x-mac-cyrillic", "x-mac-icelandic", "GEOSTD8", "armscii-8", "x-viet-tcvn5712", "VISCII", "x-viet-vps", "UTF-7", "x-imap4-modified-utf7", "UTF-16", "UTF-16BE", "UTF-16LE", "T.61-8bit", "x-user-defined", "x-mac-arabic", "x-mac-devanagari", "x-mac-farsi", "x-mac-gurmukhi", "x-mac-gujarati", "x-mac-hebrew", "Adobe-Symbol-Encoding", "x-zapf-dingbats", "x-tscii", "x-tamilttf-0", "IBM850", "IBM852", "IBM855", "IBM857", "IBM862", "IBM864", "IBM864i", "IBM869", "IBM1125", "IBM1131", "Shift_JIS", "ISO-2022-JP", "EUC-JP", "jis_0201", "x-euc-tw", "Big5", "Big5-HKSCS", "hkscs-1", "EUC-KR", "x-johab", "x-windows-949", "ISO-2022-KR", "GB2312", "gbk", "HZ-GB-2312", "gb18030", "ISO-2022-CN"]],

  mimeTypes: [
    "text/html",
    "text/html; charset=utf-8",
    "text/plain",
    "text/css",
    "text/javascript",
    "image/jpeg",
    "image/gif",
    "image/png",
    "image/mng",
    "image/*", // valid in some contexts, such as the "accept" attribute of a file upload control
    // XML
    "text/xml",
    "application/xml",
    "application/rss+xml",
    "application/xslt+xml",
    "application/vnd.mozilla.xul+xml",
    "application/xhtml+xml",
    // Not handled by the browser
    "foo/bar",
    "application/octet-stream",
    // Plugins
    "application/x-shockwave-flash",
    "application/x-test", // Mozilla's test plugin
    // Media
    "audio/mpeg",
    "audio/ogg",
    "audio/ogg; codecs=vorbis",
    "video/ogg",
    "video/ogg; codecs=\"theora, vorbis\"",
    "video/mp4",
    "video/mp4; codecs=\"avc1.42E01E, mp4a.40.2\"",
    function() { return randomThing(fuzzValues.formEncTypes); },
  ],

  formEncTypes: ["application/x-www-form-urlencoded", "multipart/form-data", "text/plain"],

  names:       [ "a", "b", "c" ], // XXX also grab IDs from the all.nodes
  namerefs:    function() { return "#" + randomThing(fuzzValues.names); },
  nameURLRefs: function() { return "url('#" + randomThing(fuzzValues.names) + "')"; },

  scriptcode: function() {
    return "/*scriptcode*/" + fuzzSubCommand("scriptcode");
  },

  metaRefreshContent: [
    function() { return randomThing(fuzzValues.unsignedNumbers); },  // refresh without redirect
    function() { return rnd(6) + ";url=" + randomThing(fuzzValues.URIs); },
  ],

  metaRefresh: function() {
    return "<meta mmmrefresh http-equiv=\"refresh\" content=\"" + randomThing(fuzzValues.metaRefreshContent) + "\">";
  },

  URIs: function () {
    if (rnd(20000) === 0) {
      return randomThing(fuzzValues.annoyingURIs);
    }
    if (rnd(100) === 0) {
      return fuzzTextDataURI(null, null);
    }
    if (rnd(60) === 0) {
      return randomThing(fuzzValues.networkURIs);
    }

    if (rnd(6) === 0) {
      return randomThing(fuzzValues.URIs) + "#" + randomThing(fuzzValues.names);
    }

    if (rnd(30) === 0) {
      return "view-source:" + randomThing([fuzzValues.dataTextHTMLURIs, fuzzValues.URIs]);
    }

    if (rnd(100) === 0) {
      return rndElt(["feed:", "pcast:"]) + randomThing(fuzzValues.URIs);
    }

    if (rnd(30) === 0) {
      // A 42-byte GIF file
      return "data:image/gif,GIF89a%01%00%01%00%80%00%00%00%00%00%FF%FF%FF!%F9%04%01%00%00%01%00%2C%00%00%00%00%01%00%01%00%00%02%01L%00%3B";
    }

    if (rnd(4) === 0) {
      return randomThing(fuzzValues.pageURIs);
    }
    if (rnd(10) === 0) {
      return location.href;
    }
    if (rnd(7) === 0) {
      return "#" + randomThing(fuzzValues.names);
    }
    if (rnd(3) === 0 && !("disableCrazyURIs" in window)) {
      return "javascript:" + fuzzSubCommand("URI") + " void 0;";
    }
    if (rnd(6) === 0) {
      return randomThing(fuzzValues.boringURIs);
    }

    return fuzzSrcTreePathToURI(randomThing(fuzzValues.srcTreeFilenames));
  },

  // Top-level reftest files, which are mostly HTML and SVG documents.
  srcTreeReftestFilenames: function() {
    try {
      return rndElt(fuzzPriv.reftestList().split("\n").slice(2));
    } catch(e) {
      dumpln("fuzzPriv.reftestList() threw?");
      return "srcTreeReftestFilenames/is/broken";
    }
  },

  // I selected these files by skimming for interesting extensions and filenames:
  //     find . | grep "reftest|crashtest" | rev | sort | rev | pbcopy

  // Plus a few files from mochitest, where I couldn't find an appropriate file from reftest.
  // In Tinderbox builds, these require descending into tests/mochitest/tests/ instead of tests/reftest/tests/ :(

  // It would be nice to include more files, using the extension or a periodic task to crawl
  // all reftest/crashtest/[mochitest??] directories for things that aren't manifests.
  // This would get the -inner.html files which often do evil things when loaded in frames :)

  // It would be nice to mangle these files (file format fuzzing).
  // It would be nice to convert these files to data: URIs.

  // Various reftest files that are safe to load as pages.
  srcTreePageFilenames: [
    function() { return randomThing(fuzzValues.srcTreeReftestFilenames); },

    [
      // Sound
      "content/media/test/crashtests/sound.ogg",

      // Images & Animations
      "testing/crashtest/images/animfish.gif",
      "layout/reftests/bugs/mozilla-banner.gif",
      "layout/reftests/image/image-exif-90-deg-flip.jpg",
      "image/test/reftest/gif/transparent-animation.gif",
      "image/test/reftest/jpeg/jpg-progressive.jpg",
      "image/test/reftest/color-management/color-curv.png",
      "image/test/reftest/apng/bug411852-1.png",
      "content/canvas/test/image_anim-gr.png",
      "../../mochitest/tests/content/canvas/test/image_anim-gr.png", // terrible hack for Tinderbox builds

      // Videos
      "layout/reftests/ogg-video/black140x100.ogv",
      "layout/reftests/ogg-video/black100x100-aspect3to2.ogv",
      "layout/reftests/ogg-video/black29x19offset.ogv",
      "layout/reftests/webm-video/frames.webm",

      // Plain text
      "layout/reftests/text-svgglyphs/resources/rubbish.txt",

      // Feed
      "toolkit/components/places/tests/chrome/sample_feed.atom",
      "../../mochitest/tests/toolkit/components/places/tests/chrome/sample_feed.atom", // terrible hack for Tinderbox builds
    ],
  ],

  srcTreeFontFilenames: [
    "layout/reftests/fonts/markA.eot",
    "layout/reftests/fonts/markB.eot",
    "layout/reftests/fonts/markA-redirect.ttf",
    "layout/reftests/fonts/Ahem.ttf",
    "layout/reftests/fonts/graphite/grtest-simple.gdl",
    "layout/reftests/fonts/graphite/grtest-template.ttx",
    "layout/reftests/fonts/graphite/grtest-ref.ttx",
    "layout/reftests/fonts/gsubtest/gsubtest-shell.ttx",
    "layout/reftests/fonts/graphite/grtest-ot.ttx",
    "layout/reftests/fonts/graphite/grtest-ot-only.ttx",
    "layout/reftests/fonts/DejaVuSansMono.woff",
    "layout/reftests/text-svgglyphs/resources/svg.woff",
    "layout/reftests/text-svgglyphs/resources/nosvg.woff",
    "layout/reftests/text-svgglyphs/resources/rubbish.woff",
  ],

  // Various reftest files.
  srcTreeFilenames: [
    function() { return randomThing(fuzzValues.srcTreePageFilenames); },
    function() { return randomThing(fuzzValues.srcTreeFontFilenames); },

    [
      // RDF
      "content/xul/templates/src/crashtests/330010-1.rdf",
      "content/xul/templates/src/crashtests/330012-1.rdf",
      "content/xul/content/crashtests/236853.rdf",
      "content/xul/templates/src/crashtests/257752-1-recursion.rdf",

      // XBL
      "layout/reftests/svg/svg-integration/mask-html-xbl-bound-01.xbl",

      // XSLT
      "content/test/reftest/xml-stylesheet/svg_passer.xslt",
      "content/xslt/crashtests/528300.xml",

      // CSS
      "image/test/reftest/ImageDocument.css",
      "layout/reftests/css-charset/test-charset-utf-16-be-bom.css",
      "layout/reftests/flexbox/ahem.css",

      // JavaScript
      "content/base/crashtests/700512-worker.js",
      "layout/reftests/table-dom/tableDom.js",
    ],
  ],

  annoyingURIs: [
    "http://www.squarefree.com/stats/fuzz", // often triggers an http auth dialog
    "https://www.squarefree.com/stats/fuzz", // often triggers an http auth dialog
    "aim:yaz", // often triggers an "external protocol request" dialog
    "foop:yaz", // often triggers an unknown protocol thingie
    "http://htmledit.squarefree.com/special_files/empty.zip",
    "http://htmledit.squarefree.com/flashAbout_info_small.swf",
    "http://www.squarefree.com/spampede/Spampede.class", // java
    "http://www.squarefree.com/spampede/", // page that uses java
    "about:memory", // content is not allowed to link or load
    "ws://example.mozilla.com/", // WebSocket protocol
    "ftp://ftp.mozilla.org/pub/mozilla.org/firefox/releases/0.9.2/shellblock.xpi",
    "ftp://ftp.mozilla.org/pub/l10n-kits/netHelp-4x-tools.zip",
  ],

  boringURIs: [
    // Special schemes
    "about:blank",
    "about:srcdoc",
    "about:mozilla",
    "about:rights",
    "data:text/html,",
    "data:text/html,<body onload='" + escalationAttempt + "'>",
    "data:image/png,",
    "data:",
    "javascript:5555",
    "javascript:" + escalationAttempt,
    "javascript:'QQQQ' + String.fromCharCode(0) + 'UUUU'",
  ],

  networkURIs: [
    // Use the network, have a different origin
    "http://htmledit.squarefree.com/", // frames and scripts
    "http://www.squarefree.com/shell", // redirect
    "http://squarefree.com/shell", // two redirects
    "http://squarefree.com/bookmarklets", // three redirects, the last going to https
    "http://www.squarefree.com/bookmarklets", // two redirects, the last going to https
    "http://www.squarefree.com/bookmarklets/",
    "https://www.squarefree.com/bookmarklets/",
    "http://ftp.mozilla.org/",
    "ftp://ftp.mozilla.org/",
    "about:credits", // secretly loads from mozilla.org
    "about:home", // loads snippets from mozilla.org?
  ],

  // URLs that are safe to load as frames, in new tabs, etc.
  pageURIs: function() {
    if (rnd(2000) === 0)
      return randomThing(fuzzValues.URIs);

    if (rnd(30) === 0) {
      return "view-source:" + randomThing([fuzzValues.dataTextHTMLURIs, fuzzValues.pageURIs]);
    }

    if (rnd(30) === 0) {
      return "#" + randomThing(fuzzValues.names);
    }
    if (rnd(6) === 0) {
      return randomThing(fuzzValues.pageURIs) + "#" + randomThing(fuzzValues.names);
    }

    return randomThing([
      function() { return fuzzSrcTreePathToURI(randomThing(fuzzValues.srcTreePageFilenames)); },
      fuzzValues.dataTextPlainURIs,
      fuzzValues.dataTextHTMLURIs,
      fuzzValues.dataXMLURIs,
      "404" // cross-compartment excitement!
    ]);
  },

  doctypeDeclarations: [
    // standards
    "<!DOCTYPE html>",
    '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">',
    // almost-standards
    "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01 Transitional//EN\" \"http://www.w3.org/TR/html4/loose.dtd\">",
    // quirks
    '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">',
    "",
  ],

  dataTextPlainURIs: function() {
    var text = rnd(2) ? randomThing(fuzzValues.texts) : "" + fuzzTotallyRandomValue();
    return fuzzTextDataURI("text/plain", text);
  },

  dataTextHTMLURIs: function() {
    var docType = randomThing(fuzzValues.doctypeDeclarations);
    var html = randomThing(fuzzValues.htmlMarkup);
    return fuzzTextDataURI("text/html", docType + html);
  },

  dataXMLURIs: function() {
    var xmlMimeType = rndElt(["application/xml", "text/xml", "application/xhtml+xml", "image/svg+xml", "application/vnd.mozilla.xul+xml"]);
    var xml = randomThing(fuzzValues.xmlMarkup);
    return fuzzTextDataURI(xmlMimeType, xml);
  },

  htmlMarkup: [
    function() { try { return serializeHTML(all.nodes[randomElementIndex()], false); } catch(e) { return ""; } },
    function() { return fuzzValues.generateHTML(rnd(7)); },
    function() { return fuzzValues.xmlMarkup(); },
    function() { return randomThing(fuzzValues.metaRefresh) + randomThing(fuzzValues.htmlMarkup); },
    function() { return fuzzValues.modifyText(randomThing(fuzzValues.htmlMarkup)); }
  ],

  xmlMarkup: function() {
    var x;
    if (rnd(10) === 0) {
      return "<script xmlns='http://www.w3.org/1999/xhtml'><![CDATA[" + fuzzSubCommand("xmlscript") + "]]><\/script>";
    }
    try {
      x = (new XMLSerializer).serializeToString(all.nodes[randomElementIndex()]);
    } catch(e) {
      x = "<oops/>";
    }
    if (rnd(10) === 0) {
      x = fuzzValues.modifyText(x);
    }
    return x;
  },

  texts: [
    [
      "",
      "foo",
      "Zapfino", // chosen for its whole-word ligature in the Zapfino font
      "ijsland", // lang="nl" casing
      "The quick brown fox jumps over the lazy dog.",
      "su\u00ADper\u00ADcal\u00ADifrag\u00ADilis\u00ADtic\u00ADex\u00ADpi\u00ADali\u00ADdo\u00ADcious",
      " x",
      "x ",
      " x ",
      "%n%n%n%n%n%n%n",
      "%s%s%s%s%s%s%s",
      "fi", // a ligature in many fonts for English

      // Combining marks: composing, non-composing, excessive ("supercombiner")
      'X\u0301', // use of a combining acute accent that does not compose
      'a\u0301', // use of a combining acute accent that composes
      "u\u0300\u0301\u0302\u0303\u0304\u0305\u0306\u0307\u0308\u0309\u030a\u030b\u030c\u030d\u030e\u030f\u0310\u0311\u0312\u0313\u0314\u0315\u0316\u0317\u0318\u0319\u031a\u031b\u031c\u031d\u031e\u031f\u0320\u0321\u0322\u0323\u0324\u0325\u0326\u0327\u0328\u0329\u032a\u032b\u032c\u032d\u032e\u032f\u0330\u0331\u0332\u0333\u0334\u0335\u0336\u0337\u0338\u0339\u033a\u033b\u033c\u033d\u033e\u033f\u0340\u0341\u0342\u0343\u0344\u0345\u0346\u0347\u0348\u0349\u034a\u034b\u034c\u034d\u034e\u034f\u0350\u0351\u0352\u0353\u0354\u0355\u0356\u0357\u0358\u0359\u035a\u035b\u035c\u035d\u035e\u035f\u0360\u0361\u0362\u0363",

      '\uD83C\uDDFA\uD83C\uDDF8', // National flag of the United States: 4 utf-16 thingies, making 2 characters, shown as 1 glyph
    ],
    function() { return fuzzValues.stolenText(); },
    function() { return fuzzValues.mediumMixedString(); },
    function() { return fuzzValues.longRepeatedString(); },
    function() { return randomThing(fuzzValues.chars); },
    function() { var s = rndElt(all.strings); try { if (s) return "" + s; } catch(e) { } return ""; }
  ],
  chars: [
    function() { return fuzzValues.bmpChars(); },
    function() { return fuzzValues.surrogatePairs(); },
    function() { return fuzzValues.syntaxChars(); },
    function() { return fuzzValues.nearbyChars(); },
    function() { return fuzzCodePointToUTF16(rndElt(fuzzValues.layoutCodePoints)); }
  ],

  nearbyChars: (function () {
    var lastCodePoint = 0x20;

    function next()
    {
      switch(rnd(30)) {
      case 0:  return rnd(0x100); // ASCII+
      case 1:  return rndElt(fuzzValues.layoutCodePoints);
      case 2:
      case 3:
      case 4:  return rnd(0x10000); // BMP
      case 5:  return rnd(0x110000); // All 17 planes
      default:
        var newCodePoint = lastCodePoint + (rnd(3)-2) * Math.floor(Math.pow(2, rnd.rndReal() * 10));
        if (newCodePoint < 0)
          newCodePoint = 0x20;
        if (newCodePoint >= 0x110000)
          newCodePoint = 0xFFFD;
        return newCodePoint;
      }
    }

    return function() {
      lastCodePoint = next();
      return fuzzCodePointToUTF16(lastCodePoint);
    };
  })(),

  syntaxChars: function() {
    var s = "'\"\\!@#$%^&*()_+-=[]{}|:;,./<>?`~ 5x\n\r\0";
    return s.charAt(rnd(s.length));
  },
  surrogatePairs: function() {
    var highSurrogate = 0xD800 + rnd(400);
    var lowSurrogate = 0xDC00 + rnd(400);
    return String.fromCharCode(highSurrogate) + String.fromCharCode(lowSurrogate);
  },

  layoutCodePoints: [
    0x0000, // null
    0x0009, // tab
    0x000A, // line feed
    0x000D, // carriage return

    0x0020, // space
    0x0032, // '2'
    0x0042, // 'B'
    0x0053, // 'S'
    0x0062, // 'B'
    0x0073, // 's'
    0x00A0, // non-breaking space

    0xFF33, // FULLWIDTH LATIN CAPITAL LETTER S
    0x30AB, // KATAKANA LETTER KA
    0x30F5, // KATAKANA LETTER SMALL KA
    0xFF76, // HALFWIDTH KATAKANA LETTER KA

    0x0049, // I
    0x0069, // i
    0x0130, // LATIN_CAPITAL_LETTER_I_WITH_DOT_ABOVE
    0x0131, // LATIN_SMALL_LETTER_DOTLESS_I

    0x03A3, // GREEK_CAPITAL_LETTER_SIGMA, which can be lowercased in two ways

    0x005C, // backslash, but in some countries, represents local currency symbol (e.g. yen)
    0x00DF, // German letter Eszett (html entity "szlig"), which uppercases as "SS".

    0x0BCC, // a Tamil character that is displayed as three glyphs

    // http://unicode.org/charts/PDF/U2000.pdf

    0x200B, // zero-width space
    0x200C, // zero-width non-joiner
    0x200D, // zero-width joiner
    0x200E, // left-to-right mark
    0x200F, // right-to-left mark

    0x002D, // hyphen (or minus)
    0x00AD, // soft hyphen
    0x2011, // non-breaking hyphen
    0x2027, // hyphenation point

    0x2028, // line separator
    0x2029, // paragraph separator
    0x202A, // left-to-right embedding
    0x202B, // right-to-left embedding
    0x202C, // pop directional formatting
    0x202D, // left-to-right override
    0x202E, // right-to-left override
    0x202F, // narrow no-break space

    0x1680, // OGHAM SPACE MARK
    0x205F, // MEDIUM MATHEMATICAL SPACE

    0x2060, // word joiner
    0x2061, // function application (one of several invisible mathematical operators)

    // http://unicode.org/charts/PDF/U3000.pdf

    0x3000, // ideographic space (CJK)

    // http://unicode.org/charts/PDF/U0300.pdf

    0x0301, // combining acute accent (if it appears after "a", it turns into "a" with an accent)
    0x00E1, // the result of composing "a" with an acute accent

    // Arabic has the interesting property that most letters connect to the next letter.
    // Some code calls this "shaping".
    0x0643, // arabic letter kaf
    0x0645, // arabic letter meem
    0x06CD, // arabic letter yeh with tail
    0xFDDE, // invalid unicode? but somehow associated with arabic.

    // "Characters whose normalization forms under NFC, NFD, NFKC, and NFKD are all different"
    // http://unicode.org/faq/normalization.html#6
    0x03D3,
    0x03D4,
    0x1E9B,

    // Characters with especially high expansion factors when they go through various unicode "normalizations"
    // http://web.lookout.net/2009/04/unicode-security-attacks-and-test-cases.html
    // http://unicode.org/faq/normalization.html#12
    0x1F82,
    0xFDFA, // ARABIC LIGATURE SALLALLAHOU ALAYHE WASALLAM
    0x1D160, // MUSICAL SYMBOL EIGHTH NOTE
    0xFB2C,
    0x0390,

    // Characters with especially high expansion factors when lowercased or uppercased
    0x023A,
    //0x0390, // also listed above

    0xFDFD, // ARABIC LIGATURE BISMILLAH AR-RAHMAN AR-RAHEEM, which is rather wide

    0xDC1D, // a low surrogate
    0xDB00, // a high surrogate

    // See bug 732696
    0x1112C, // CHAKMA VOWEL SIGN E

    // Color emoji
    0x1F60E, // SMILING FACE WITH SUNGLASSES

    // "Regional Indicators" that can combine to make the national flags of the United States, Germany, and Spain
    0x1F1E9, // Region 'D'
    0x1F1EA, // Region 'E'
    0x1F1FA, // Region 'U'
    0x1F1F8, // Region 'S'

    // Mats Palmgren suggested also looking at bidi character groups:
    // http://bonsai.mozilla.org/cvsblame.cgi?file=/mozilla/layout/base/nsBidiUtils.h&rev=1.11&root=/cvsroot&mark=197-244#197
  ],

  bmpChars: function() {
    return String.fromCharCode(rnd(65536));
  },

  stolenText: function() {
    // Could integrate with all.strings
    if (!window.all.nodes) return ""; // possible with html-round-trip.html
    var node = rndElt(all.nodes);
    try { return "" + node.data; } catch(e) { return ""; }
  },

  modifyText: function(s) {
    s = typeof s == "string" ? s : ""; // needed for fuzzTotallyRandomValue

    var L = s.length;

    // 0 <= i <= j <= L
    var i = rnd(L + 1);
    var j = i + rnd(L + 1 - i);

    switch (rnd(10)) {
    case 0:
      return randomThing(fuzzValues.texts);
    case 1:
      return s.substr(0, i);
    case 2:
      return s.slice(i);
    case 3:
      // Elide i..j
      return s.substr(0, i) + s.slice(j);
    case 4:
      // Modify numbers in the string
      return fuzzValues.modifyNumbersInString(s);
    case 5:
      // Insert a string at position i
      return s.substr(0, i) + randomThing(fuzzValues.texts) + s.slice(i);
    case 6:
      // Modify a character at position i
      return s.substr(0, i) + randomThing(fuzzValues.chars) + s.slice(i + 1);
    case 7:
      // Duplicate the string
      return s + rndElt(["", ",", " "]) + s;
    default:
      // Insert a character at position i
      return s.substr(0, i) + randomThing(fuzzValues.chars) + s.slice(i);
    }
  },

  modifyNumbersInString: function(s) {
    s = typeof s == "string" ? s : ""; // needed for fuzzTotallyRandomValue
    var pctA = rnd(100);
    var pctB = rnd(100);
    var replaceNumber = function(q) { return rnd(100) > pctA ? q : randomThing(fuzzValues.numbers); };
    var replaceUnit = function(q) { return rnd(100) > pctB ? q : randomThing(fuzzValues.numbersWithUnits); };
    s = s.replace(/-?\d+(\.\d+)?(px|em|ch|cm|in|rem)/g, replaceUnit);
    s = s.replace(/-?\d+(\.\d+)?/g, replaceNumber);
    return s;
  },

  longRepeatedString: function () {
    var x = randomThing(fuzzValues.chars);
    var doublings = rnd(4) * rnd(3) * rnd(3);
    for (var i = 0; i < doublings; ++i)
      x = x + x;
    if (rnd(5) === 0)
      x = x + x.substr(0, rnd(x.length));
    return x;
  },

  mediumMixedString: function () {
    var t = fuzzValues.chars;
    if (rnd(2))
      t = rndElt(t); // pick a strategy and stick to it
    var s = "";
    var len = rnd(1000) * rnd(10) + rnd(10);
    for (var i = 0; i < len; ++i)
      s += randomThing(t);
    return s;
  },

  percentEscapedBytes: function()
  {
    var s = "";
    var hex = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e", "f"];
    var len = rnd(200);
    for (var i = 0; i < len; ++i) {
      s += "%" + rndElt(hex) + rndElt(hex);
    }
    return s;
  },

  // http://mxr.mozilla.org/mozilla-central/source/layout/style/nsCSSPseudoElementList.h (plus secret extra colon)
  cssPseudoElements: [
    ":after",
    ":before",
    ":first-letter",
    ":first-line",
    "::-moz-selection",
    "::-moz-focus-inner",
    "::-moz-focus-outer",
    "::-moz-placeholder",
    "::-moz-list-bullet",
    "::-moz-list-number",
    "::-moz-hframeset-border",
    "::-moz-vframeset-border",
    "::-moz-math-stretchy",
    "::-moz-math-anonymous",
    "::-moz-progress-bar",
    "::-moz-range-track",
    "::-moz-range-thumb",
    "::-moz-range-progress",
    "::-moz-meter-bar",
  ],

  // Anonymous boxes, in contrast, are only available to privileged stylesheets.
  // http://mxr.mozilla.org/mozilla-central/source/layout/style/nsCSSAnonBoxList.h

  // http://www.w3.org/TR/css3-selectors/
  cssPseudoClasses: [

    // List from http://mxr.mozilla.org/mozilla-central/source/layout/style/nsCSSPseudoClassList.h
    ":empty",
    ":-moz-only-whitespace",
    ":-moz-empty-except-children-with-localname",
    ":lang",
    function() { return ":lang(" + randomThing(fuzzValues.languages) + ")"; },
    ":-moz-bound-element",
    ":root",
    ":scope",
    ":-moz-any",
    ":first-child",
    ":-moz-first-node",
    ":last-child",
    ":-moz-last-node",
    ":only-child",
    ":first-of-type",
    ":last-of-type",
    ":only-of-type",
    ":nth-child",
    ":nth-last-child",
    ":nth-of-type",
    ":nth-last-of-type",
    ":-moz-has-handlerref",
    ":-moz-is-html",
    ":-moz-system-metric",
    ":-moz-locale-dir",
    ":-moz-locale-dir(ltr)",
    ":-moz-locale-dir(rtl)",
    ":-moz-lwtheme",
    ":-moz-lwtheme-brighttext",
    ":-moz-lwtheme-darktext",
    ":-moz-window-inactive",
    ":-moz-table-border-nonzero",
    ":not",
    ":link",
    ":-moz-any-link",
    ":visited",
    ":active",
    ":checked",
    ":disabled",
    ":enabled",
    ":focus",
    ":hover",
    ":-moz-drag-over",
    ":target",
    ":indeterminate",
    ":-moz-full-screen",
    ":-moz-full-screen-ancestor",
    ":-moz-focusring",
    ":-moz-broken",
    ":-moz-user-disabled",
    ":-moz-suppressed",
    ":-moz-loading",
    ":-moz-type-unsupported",
    ":-moz-handler-clicktoplay",
    ":-moz-handler-disabled",
    ":-moz-handler-blocked",
    ":-moz-handler-crashed",
    ":-moz-math-increment-script-level",
    ":required",
    ":optional",
    ":valid",
    ":invalid",
    ":in-range",
    ":out-of-range",
    ":default",
    ":-moz-read-only",
    ":-moz-read-write",
    ":-moz-submit-invalid",
    ":-moz-ui-invalid",
    ":-moz-ui-valid",

    // Some examples with parameters
    ":nth-child(odd)",
    ":nth-child(even)",
    ":nth-last-child(-n+2)",
    ":nth-last-child(odd)",
    ":nth-of-type(2n+1)",
    ":nth-of-type(2n)",
    ":nth-last-of-type(-n+2)",
    ":nth-last-of-type(n+2)",
    ":not(:last-of-type)",
    ":-moz-system-metric(scrollbar-start-backward)",
    ":-moz-system-metric(scrollbar-start-forward)",
    ":-moz-system-metric(scrollbar-end-backward)",
    ":-moz-system-metric(scrollbar-end-forward)",
    ":-moz-system-metric(scrollbar-thumb-proportional)",
    ":-moz-system-metric(foo)",
  ],

  cssCombinators: [" ", " > ", " ~ ", " + ", " - "],

  cssSelectorBases: ["*", "div", ":not(div)", "#a", ":not(#a)"],

  cssSelectorParts: function() {
    var sel = randomThing(fuzzValues.cssSelectorBases);
    while (rnd(3) === 0)
      sel += randomThing(fuzzValues.cssPseudoClasses);
    return sel;
  },

  cssSelectors: function() {
    var sel = randomThing(fuzzValues.cssSelectorParts);
    while (rnd(2)) {
      sel += randomThing(fuzzValues.cssCombinators) + randomThing(fuzzValues.cssSelectorParts);
    }
    if (rnd(5) === 0) {
      sel += randomThing(fuzzValues.cssPseudoElements);
    }
    return sel;
  },

};

function fuzzTotallyRandomValue()
{
  var fuzzValueKeys = getKeysFromHash(fuzzValues);
  var k = rndElt(fuzzValueKeys);
  return randomThing(fuzzValues[k]);
}


function fuzzSrcTreePathToURI(path)
{
  if (rnd(20) && location.protocol == "file:") {
    // Try to load the file locally.

    try {
      return "file:///" + fuzzPriv.reftestFilesDirectory() + "/" + path;
    } catch(e) {
      dumpln("reftestFilesDirectory() threw, so we'll load the file from hgweb or mxr");
    }
  }

  // We decided not to load the file locally (or were unable to).
  // XXX it would be more polite to use a local server than pounding mxr/hg
  // XXX that would also allow supporting multipart/x-mixed-replace (e.g. image/test/reftest/jpeg/webcam-simulacrum.mjpg and custom evil)

  var protocol = rndElt(["http", "https"]);
  if (rnd(3)) {
    // hgweb gives the right mime type for most files
    return protocol + "://hg.mozilla.org/mozilla-central/raw-file/default/" + path;
  } else {
    // MXR gives text/plain for most files
    return protocol + "://mxr.mozilla.org/mozilla-central/source/" + path + "?raw=1";
  }
}

function fuzzCodePointToUTF16(c)
{
  if (c < 0x10000) {
    return String.fromCharCode(c);
  } else {
    // Create a surrogate pair.
    var v = c - 0x10000;
    var lo = v % 0x400;
    var hi = (v - lo) / 0x400;
    return String.fromCharCode(0xD800 + hi) + String.fromCharCode(0xDC00 + lo);
  }
}

function fuzzTextDataURI(mime, text)
{
  // Creates a data: URL with a random charset

  if (mime == undefined || rnd(10) === 0)
    mime = randomThing(fuzzValues.mimeTypes);

  if (text == undefined) {
    text = randomThing(fuzzValues.texts);
  } else if (rnd(10) === 0) {
    text = fuzzValues.modifyText(text);
  }

  if (text.length > 100000)
    return "data:text/plain,Too-long input";

  if (fuzzBlacklistVeto(text))
    return "data:text/plain,Vetoed";

  function uri_escape(s)
  {
    try {
      return encodeURIComponent(s);
    } catch(e) { }
    return "Non-unicode input";
  }

  function probablyCharset(c)
  {
    switch(rnd(10)) {
      case 0:  return "";
      case 1:  return ";charset=" + randomThing(fuzzValues.charsets);
      default: return ";charset=" + c;
    }
  }

  function utf16be_escape(s)
  {
    // Take advantage of JS strings actually being made of UTF-16 pieces
    var r = "";
    for (var i = 0; i < s.length; ++i) {
      var c = s.charCodeAt(i);
      var hexes = c.toString(16);
      while (hexes.length < 4) hexes = "0" + hexes;
      r += "%" + hexes[0] + hexes[1] + "%" + hexes[2] + hexes[3];
    }
    return r;
  }

  function echoServerURI(fullMime, responseBody)
  {
    return fuzzEchoRequest('200 OK', ['Content-Type: ' + fullMime, 'Connection: Close'], responseBody)
  }

  function fuzzHTTPRedirect(uri)
  {
    // There are four types of HTTP redirects (30x codes that include a Location header).
    // http://blogs.msdn.com/b/tijujohn/archive/2012/06/01/different-redirect-http-response-status-codes-and-how-the-browser-should-react-301-vs-302-vs-303-vs-307.aspx
    var redirectStatuses = ["301 Moved Permanently", "302 Found", "303 See Other", "307 Temporary Redirect"];

    return fuzzEchoRequest(rndElt(redirectStatuses), ['Location: ' + uri, 'Connection: Close'], "");
  }

  function fuzzEchoRequest(responseStatus, responseHeaders, responseBody)
  {
    if (rnd(10) == 0) {
      // http://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html
      // http://en.wikipedia.org/wiki/List_of_HTTP_status_codes
      responseStatus = rndElt([100, 101, 200, 201, 202, 203, 204, 205, 206, 300, 301, 302, 303, 304, 305, 306, 307, 400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 500, 501, 502, 503, 504, 505]);
    } else if (rnd(300) == 0) {
      if (rnd(20)) responseStatus = '401 Not Authorized';
      if (rnd(20)) responseHeaders.push('WWW-Authenticate: Basic realm="Fuzzland"');
    }

    // TODO: Generic array manipulations (shuffle, duplicate, omit) on responseHeaders
    // TODO: Add random nonsense headers

    for (var i = 0; i < responseHeaders.length; ++i) {
      if (rnd(10) == 0) {
        responseHeaders[i] = fuzzValues.modifyText(responseHeaders[i]);
      }
    }

    var fullResponse = "HTTP/1.1 " + responseStatus + "\r\n" + responseHeaders.join("\r\n") + "\r\n" + "\r\n" + responseBody;
    return "http://localhost:9606/?delay=" + rnd(1500) + "&response=" + btoa(unescape(uri_escape(fullResponse)));
  }

  function f()
  {
    switch(rnd(4)) {
      case 0:
        // Base64-encoded UTF-8
        return "data:" + mime + probablyCharset("utf-8") + ";base64," + btoa(unescape(uri_escape(text)));
      case 1:
        // Optimistic, partially-escaped UTF-8
        return "data:" + mime + probablyCharset("utf-8") + "," + uri_escape(text);
      case 2:
        // Fully-percent-escaped UTF-16BE without a BOM
        return "data:" + mime + probablyCharset("utf-16be") + "," + utf16be_escape(text);
      case 3:
        // Complete nonsense (test the charset decoders)
        return "data:" + mime + (rnd(2) ? ";charset=" + randomThing(fuzzValues.charsets) : "") + "," + fuzzValues.percentEscapedBytes();
      default:
        // Bounce it off a server instead (requires echo_server to be running)
        //return echoServerURI(mime + probablyCharset("utf-8"), text);
        return "data:text/plain,1";
    }
  }

  var uri = f();
  while (uri.length < 100000 && rnd(2))
    uri = fuzzHTTPRedirect(uri)
  return uri;
}

function rndBoolStr() { return rndElt(["true", "false"]); }


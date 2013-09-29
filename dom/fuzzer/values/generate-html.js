fuzzValues.generateHTML = (function() {

  // http://www.whatwg.org/specs/web-apps/current-work/multipage/parsing.html
  // http://www.whatwg.org/specs/web-apps/current-work/multipage/tokenization.html#tree-construction

  var scriptOptions = ["", "", "", " async", " async defer", " defer"];

  var funIngredients = [
    // From a 'radware' bug:
    "<s>",
    "<form>a<\/form>",
    "<iframe><\/iframe>",
    "<script src=a><\/script>",
    "<form><\/form>",
    "<table>",
    "<optgroup>",
    function() {
      var scriptCode = fuzzSubCommand("scriptsrc");
      return '<script' + Random.index(scriptOptions) + ' src="' + quoteEscape(fuzzTextDataURI('text/javascript', scriptCode)) + '"><\/script>';
    },

    function() {
      return "<script" + Random.index(scriptOptions) + ">" + fuzzSubCommand("inlinescript") + "<\/script>";
    },

    function() {
      return Random.pick(fuzzValues.doctypeDeclarations);
    },

    function() { return "<meta charset='" + Random.pick(fuzzValues.charsets) + "'>"; },
    "<!---->",
    "<!--x-->",
  ];

  var funTags = ["annotation-xml", "foreignObject", "svg", "math", "html"];

  function makeOpenTag(t, source)
  {
    var s = "<" + t;
    var numAttrs = rnd(3) * rnd(3);
    for (var i = 0; i < numAttrs; ++i)
      s += makeAttribute(t, source);

    s += ">";
    return s;
  }

  function makeCloseTag(t)
  {
    return "<" + "/" + t + ">";
  }

  function makeText()
  {
    return Random.pick(fuzzValues.texts);
  }


  function makeAttribute(tag, source)
  {
    var attr; // a string or [string, value-generator] pair
    var vg; // a thing that can be passed to Random.pick to get a value string or number out
    var value; // a string or number

    var tagToAttrs = source.elemHash;

    // Sometimes, pretend it's a different tag.
    // This lets us get at tag-specific values!
    if (rnd(10) === 0) {
      tag = Random.index(source.elemList);
      // dumpln("Pretending it's a: " + tag);
    }

    // This typeof thing is because if the tag name is "filter", and you look in the MathML tag array, you could get an array extra (argh!) (does that make sense?) (array/hash confusion?)
    var choices = tagToAttrs[tag];
    if ((typeof choices == "object") && (choices.length) && (rnd(10) !== 0)) {
      attr = Random.index(choices);
    } else {
      attr = Random.index(source.attrList);
    }

    if (typeof attr == "string") {
      vg = source.attrHash[attr];
      if (vg == null) {
        // dumpln("Eep, I know " + namespaceURI + " '" + tag + "' has an attribute '" + attr + "' but I don't know values for that attribute.");
      }
    } else {
      // To allow tag-specific values, tagToAttrs sometimes give us
      // an [attr, values] pair instead of just an attr.
      vg = attr[1];
      attr = attr[0];
    }

    if (vg != null && rnd(5) !== 0) {
      value = Random.pick(vg);
    } else {
      var otherAttr = Random.index(source.attrList);
      value = Random.pick(source.attrHash[otherAttr]);
    }

    // dumpln("% " + uneval(attr) + " " + uneval(value));
    return " " + attr + "=\"" + htmlAttrEscape("" + value) + "\"";
  }

  function htmlEscape(s)
  {
    s = s.replace(/&/g,'&amp;');
    s = s.replace(/>/g,'&gt;');
    s = s.replace(/</g,'&lt;');
    return s;
  }

  function quoteEscape(s)
  {
    s = s.replace(/"/g,'&quot;');
    return s;
  }

  function htmlAttrEscape(s)
  {
    return quoteEscape(htmlEscape(s));
  }

  function makeHTML(n)
  {
    n = Math.min(n, 20);

    var tagStack = [];
    var s = "";
    if (rnd(2))
      s += Random.pick(fuzzValues.doctypeDeclarations);

    for (var i = 0; i < n; ++i) {
      var source = Random.pick([fuzzerHTMLAttributes, fuzzerSVGAttributes, fuzzerMathMLAttributes]);
      var el = rnd(4) ? Random.index(source.elemList) : Random.index(funTags);

      switch(rnd(10))
      {
        case 0:
          s += Random.index(funIngredients);
        case 1:
          s += makeOpenTag(el, source);
          break;
        case 2:
        case 3:
        case 4:
          // Just an open tag.  More likely than popping so that the stack doesn't stay tiny.
          tagStack.push(el);
          s += makeOpenTag(el, source);
          break;
        case 5:
          s += makeOpenTag(el, source);
          s += makeCloseTag(el);
          break;
        case 6:
          s += makeOpenTag(el, source);
          s += makeText();
          s += makeCloseTag(el);
          break;
        case 7:
          // Remove an element at random from tagStack, and output a close tag for it.
          // This gets at the heart of the "tag soup" issue.
          if (tagStack.length)
            el = tagStack.splice(rnd(tagStack.length), 1);
          s += makeCloseTag(el);
          break;
        case 8:
          // Remove the last element from tagStack, and output a close tag for it.
          // Possibly pop multiple tags.
          do {
            if (tagStack.length)
              el = tagStack.pop();
            s += makeCloseTag(el);
          } while (rnd(2));
          break;
        default:
          s += makeText();
          break;
      }
    }

    return s;
  }

  return makeHTML;
})();

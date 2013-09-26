/*****************************
 * SERIALIZING AS HTML/XHTML *
 *****************************/

// This function turns an HTML DOM into either HTML or XHTML.

// It might kinda work on XHTML DOMs too, but it's probably better to use
//    (new XMLSerializer).serializeToString
// rather than serializeHTML with outputXML=true if the document is XML.

// If outputXML is false, attempt to output as HTML.  (HTML enables fast-and-loose reduction, but not all DOMs can be serialized as HTML.  serializeHTML will complain about some unserializable features in HTML mode, but it won't detect things like block-in-inline and missing table parts!)

// If outputXML is true, output as XML.  (XML is more reliable in terms of re-creating an equivalent DOM.)

function serializeHTML(n, outputXML)
{
  // List from http://www.cs.tut.fi/~jkorpela/html/empty.html#html
  var emptyElements = {
    area: true,
    base: true,
    basefont: true,
    br: true,
    col: true,
    frame: true,
    hr: true,
    img: true,
    input: true,
    isindex: true,
    link: true,
    meta: true,
    param: true
  };

  var CDATAElements = {
    script: true,
    style: true
  };

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

  function serializeAttributes(n)
  {
    var i, attr;
    var r = "";
    for (i = 0; (attr = n.attributes[i]); ++i)
      r += " " + attr.name + "=\"" + quoteEscape(htmlEscape(attr.value)) + "\"";
    return r;
  }

  function hasNonTextChildren(n)
  {
    var i, child;
    for (i = 0; (child = n.childNodes[i]); ++i)
      if (child.nodeType != 3)
        return true;
    return false;
  }

  // Elements without namespace serialized in XML will get this namespace.
  var HTML_NS = "http://www.w3.org/1999/xhtml";

  function isHTML(n)
  {
    return (n.namespaceURI == null || n.namespaceURI == HTML_NS);
  }

  // uses outputXML from its closure
  function serializeSubtree(n, addXMLNSforHTML)
  {
    switch(n.nodeType) {

    case 3:
      // In XML mode, it would be "nice" to use "<![CDATA..." sometimes, but this is
      // never incorrect.
      return htmlEscape(n.data);

    case 8:
      // Should figure out what to do with double hyphens.
      return "<!--" + n.data + "-->";

    case 1:
      var needXMLNS = (addXMLNSforHTML || !isHTML(n)) && !n.hasAttribute("xmlns");
      var xmlnsString = needXMLNS ? (" xmlns=\"" + (n.namespaceURI || HTML_NS) + "\"") : "";

      var tag = n.tagName;
      if (isHTML(n))
        tag = tag.toLowerCase();
      var start = "<" + tag + xmlnsString + serializeAttributes(n) + ">";
      var end = "<" + "/" + tag + ">";

      if (!outputXML && needXMLNS) {
        // This warning is not quite right, since MathML and SVG are sometimes ok!
        dumpln("serializeHTML: Serializing an element with namespace " + n.namespaceURI + " as HTML won't work very well!");
      }

      var htmlish = !outputXML && isHTML(n);

      if (htmlish && (tag in emptyElements)) {

        if (n.childNodes.length > 0)
          dumpln("serializeHTML: Can't serialize " + tag + " element with children as HTML!");
        return start;

      } else if (htmlish && (tag in CDATAElements)) {

        if (hasNonTextChildren(n))
          dumpln("serializeHTML: Can't serialize " + tag + " element with element children as HTML!");
        // Should check for and warn if e.g. "<\/script>" appears.
        return start + n.innerHTML + end;

      } else {

        var serializedChildren = "";
        var childrenNeedXMLNS = !isHTML(n);
        var i, child;

        for (i = 0; (child = n.childNodes[i]); ++i)
          serializedChildren += serializeSubtree(n.childNodes[i], childrenNeedXMLNS);

        return start + serializedChildren + end;

      }

    default:
      dumpln("serializeHTML: Unexpected node type " + n.nodeType + ".");
      return "???";
    }
  }

  return serializeSubtree(n || document.documentElement, outputXML);
}

//setTimeout(function() { dumpln(serializeHTML(null, true)); }, 200);





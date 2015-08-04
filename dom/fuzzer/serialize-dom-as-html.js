/*****************************
 * SERIALIZING AS HTML/XHTML *
 *****************************/

// Turns an HTML DOM into HTML markup.
// Warn about common problems that prevent a faithful HTML serialization.

function serializeHTML(n)
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
    var r = "";
    for (var attr of n.attributes)
      r += " " + attr.name + "=\"" + quoteEscape(htmlEscape(attr.value)) + "\"";
    return r;
  }

  function hasNonTextChildren(n)
  {
    for (var child of n.childNodes)
      if (child.nodeType != 3)
        return true;
    return false;
  }

  var HTML_NS = "http://www.w3.org/1999/xhtml";
  var SVG_NS = "http://www.w3.org/2000/svg";
  var MATHML_NS = "http://www.w3.org/1998/Math/MathML"

  function serializeSubtree(n, contextNamespace)
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
      var tag = n.tagName;
      var namespace = n.namespaceURI || HTML_NS;
      if (namespace == HTML_NS)
        tag = tag.toLowerCase();
      var start = "<" + tag + serializeAttributes(n) + ">";
      var end = "<" + "/" + tag + ">";

      // HTML5 allows entering XML-like sections with <math> and <svg> tags.
      if (!(
          namespace == contextNamespace ||
          (contextNamespace == HTML_NS && namespace == MATHML_NS && tag == "math") ||
          (contextNamespace == HTML_NS && namespace == SVG_NS && tag == "svg")
         )) {
        dumpln("serializeHTML: What's this <" + tag + " xmlns=\"" + namespace + "\"> doing in a " + contextNamespace + " context?");
      }

      if (namespace == HTML_NS && tag in emptyElements) {
        // This element should be empty.
        if (n.childNodes.length > 0)
          dumpln("serializeHTML: Can't serialize " + tag + " element with children as HTML!");
        return start;

      } else if (namespace == HTML_NS && tag in CDATAElements) {
        // This element should have text children only.
        var inner = n.innerHTML;
        if (hasNonTextChildren(n)) {
          dumpln("serializeHTML: Can't serialize " + tag + " element with element children as HTML!");
        }
        if (inner.indexOf("<\/") != -1) {
          dumpln("serializeHTML: this <" + tag + ">'s contents may break out!");
        }
        return start + inner + end;

      } else {
        // This element can have element children.
        var serializedChildren = "";
        for (var child of n.childNodes)
          serializedChildren += serializeSubtree(child, namespace);
        return start + serializedChildren + end;

      }

    default:
      dumpln("serializeHTML: Unexpected node type " + n.nodeType + ".");
      return "???";
    }
  }

  if (n) {
    return serializeSubtree(n, HTML_NS);
  } else {
    return serializeDoctype() + serializeSubtree(document.documentElement, HTML_NS);
  }
}


function serializeDoctype()
{
  var node = document.doctype;
  if (!node)
    return "";

  // Based on http://stackoverflow.com/a/10162353/3011305
  var html = ("<!DOCTYPE "
            + node.name
            + (node.publicId ? ' PUBLIC "' + node.publicId + '"' : '')
            + (!node.publicId && node.systemId ? ' SYSTEM' : '')
            + (node.systemId ? ' "' + node.systemId + '"' : '')
            + '>');
  return html;
}


function serializeXML(n)
{
  return (new XMLSerializer()).serializeToString(n || document.documentElement);
}

//setTimeout(function() { dumpln(serializeHTML(null, true)); }, 200);

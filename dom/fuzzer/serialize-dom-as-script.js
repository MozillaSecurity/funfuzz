

/*****************************
 * SERIALIZING DOM AS SCRIPT *
 *****************************/

// Entry points:
// * serializeDOMAsScript: used at fuzzer start for creating a repro case, and during manual testcase reduction
// * scriptizeNode: used by fuzzerSlurpFrames


function serializeDOMAsScript(splitTextNodes, splitStyleAttributes)
{
  function q(note, cs)
  {
    for (var i = 0; i < cs.length; ++i) {
      var c = cs[i];
      dumpln(fuzzRecord(note, "fun: function() { " + c + " }"));
    }
  }

  if (document.documentElement) {
    q("prol", [ensureIndexed(document.documentElement) + " = document.documentElement;"]);
    q("prol", ["var root = document.documentElement; while(root.firstChild) { root.removeChild(root.firstChild); }"]);
  }

  dumpln(fuzzRecordPrefix + "// DD" + "BEGIN");

  if (document.documentElement) {
    q("seri", scriptizeAttributes(document.documentElement, "document.documentElement", splitStyleAttributes));
    q("seri", scriptizeChildren(document.documentElement, "document.documentElement", "document.documentElement", splitTextNodes, splitStyleAttributes));
  } else {
    q("seri", ["document.removeChild(document.documentElement);"]);
  }

  q("seri", scriptizeDisconnectedSubtrees(splitTextNodes, splitStyleAttributes));
  q("seri", scriptizeSelection());
}


function scriptizeDisconnectedSubtrees(splitTextNodes, splitStyleAttributes)
{
  var cs = [];
  // Look for additional nodes in o[...].
  for (var i = 0; i < o.length; ++i) {
    var n = o[i];
    if (n && n instanceof Node && n != document && !n.parentNode) {
      cs.push("/* o[" + i + "] has no parent (disconnected) */");
      cs.push(...scriptizeNode(n, "null", "o[" + i + "]", splitTextNodes, splitStyleAttributes));
    }
  }
  return cs;
}


function scriptizeSelection()
{
  var cs = [];
  var sel = window.getSelection();
  if (sel.rangeCount > 0) {
    cs.push("window.getSelection().removeAllRanges();");
    for (var i = 0; i < sel.rangeCount; ++i) {
      var range = sel.getRangeAt(i);
      var rangeStr = ensureIndexed(range);
      cs.push(rangeStr + " = document.createRange();");
      cs.push(rangeStr + ".setStart(" + ensureIndexed(range.startContainer) + ", " + range.startOffset + ");");
      cs.push(rangeStr + ".setEnd(" + ensureIndexed(range.endContainer) + ", " + range.endOffset + ");");
      cs.push("window.getSelection().addRange(" + rangeStr + ");");
    }
  }
  return cs;
}


function scriptizeText(nodeStr, funName, text, split)
{
  // Try to keep "document.write" in inline-script from being preserved,
  // because document.write blows away the document in other contexts.
  text = text.replace(/document\.write/g, "tnemucod.write");
  var cs = [];

  if (!split) {
    cs.push(nodeStr + " = document." + funName + "(" + simpleSource(text) + ");");
  } else {
    cs.push(nodeStr + " = document." + funName + "(\"\");");
    for (var i = 0; i < text.length; ++i) {
      cs.push(nodeStr + ".data += " + simpleSource(text[i]) + ";");
    }
  }

  return cs;
}


function scriptizeAttributes(n, nodeStr, splitStyleAttributes) {
  var a;
  var cs = [];
  // Adding each of the element's attributes.
  var nodeIsSVG = (n.namespaceURI == "http://www.w3.org/2000/svg");
  for (var i = 0; (a = n.attributes[i]); i++) {
    if (a.namespaceURI != "http://www.w3.org/2000/xmlns/") {
      if (splitStyleAttributes && a.name == "style" && n.style) {
        for (var prop, j = 0; (prop = n.style.item(j)); ++j) {
          var value = n.style.getPropertyValue(prop);
          var priority = n.style.getPropertyPriority(prop);
          cs.push(nodeStr + ".style.setProperty(" + simpleSource(prop) + ", " + simpleSource(value) + ", " + simpleSource(priority) + ");");
        }
      } else { // not splitting a style attribute
        var val;
        if (!nodeIsSVG && (a.name.toLowerCase() == "src" || a.name.toLowerCase() == "href")) {
          // For these URI attributes, use the corresponding getter
          // (which is always an absolute URI) rather than the
          // attribute value (which is often a relative URI)
          // for easier reduction.
          // But don't use this for SVG, because it will give you a useless SVGAnimatedString!
          val = n[a.name];
        } else {
          val = a.value;
          if (a.localName == "href" && val.charAt(0) != "#") {
            // Turn the URL absolute.  Useful for xlink:href in SVG documents.
            var tempLink = document.createElementNS("http://www.w3.org/1999/xhtml", "a");
            tempLink.href = val;
            val = tempLink.href;
          }
        }

        cs.push(nodeStr + ".setAttributeNS(" + simpleSource(a.namespaceURI) + ", " + simpleSource(a.name) + ", " + simpleSource(val) + ");");
      }
    }
  }
  return cs;
}


function scriptizeCreateElement(n, nodeStr)
{
  if (n.namespaceURI) {
    // We use localName instead of tagName because the capitalization for HTML is correct.  But this throws away the XML prefix :(
    return nodeStr + " = document.createElementNS(" + simpleSource(n.namespaceURI) + ", " + simpleSource(n.localName)  + ");";
  } else {
    // In old versions of Gecko (and possibly in other older browsers), only createElement can create working HTML elements. (See bug 393340.)
    return nodeStr + " = document.createElement(" + simpleSource(n.tagName).toLowerCase() + ");";
  }
}


function scriptizeChildren(n, nodeStr, ancestryPathStr, splitTextNodes, splitStyleAttributes)
{
  var cs = [];
  for (var i = 0; i < n.childNodes.length; ++i) {
    var child = n.childNodes[i];
    var childStr = ensureIndexed(child);
    cs.push(...scriptizeNode(child, childStr + " || " + ancestryPathStr, splitTextNodes, splitStyleAttributes));
    cs.push("(" + ancestryPathStr + ").appendChild(" + childStr + ");");
  }
  return cs;
}


function scriptizeNode(n, ancestryPathStr, splitTextNodes, splitStyleAttributes)
{
  var nodeStr = ensureIndexed(n);
  var cs = [];

  switch (n.nodeType) {
    case Node.ELEMENT_NODE:
      cs.push(scriptizeCreateElement(n, nodeStr));
      cs.push(...scriptizeAttributes(n, nodeStr, splitStyleAttributes));
      break;

    case Node.DOCUMENT_FRAGMENT_NODE:
      cs.push(nodeStr + " = document.createDocumentFragment();");
      break;

    case Node.DOCUMENT_NODE:
      cs.push(nodeStr + " = document.implementation.createDocument('', '', null);");
      break;

    case Node.COMMENT_NODE:
      cs.push(nodeStr + " = document.createComment(" + simpleSource(n.data) + ");");
      break;

    case Node.TEXT_NODE:
      cs.push(...scriptizeText(nodeStr, "createTextNode", n.data, splitTextNodes));
      break;

    case Node.CDATA_SECTION_NODE:
      cs.push(...scriptizeText(nodeStr, "createCDATASection", n.data, splitTextNodes));
      break;

    default:
      dumpln("scriptizeNode: " + nodeStr + " has unrecognized node type " + n.nodeType + ".");
  }

  cs.push(...scriptizeChildren(n, nodeStr, ancestryPathStr, splitTextNodes, splitStyleAttributes));

  return cs;
}


function ensureIndexed(n)
{
  var ix = Things.findIndex(n);
  if (ix === -1) {
    try {
      if (n.getAttribute && n.getAttribute("fuzzskip")) {
        // e.g. for adding a base href tag
        return null;
      }
    } catch(e) {
      /* A native anonymous node? */
    }
    var description = "???";
    try {
      description = Object.prototype.toString.call(n);
    } catch(e) {
    }
    ix = o.length;
    o[ix] = n;
    dumpln("Indexed a " + description + " as o[" + ix + "].");
  }
  return "o[" + ix + "]";
}

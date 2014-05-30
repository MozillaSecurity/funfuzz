

/*****************************
 * SERIALIZING DOM AS SCRIPT *
 *****************************/


function serializeDOMAsScript(root, splitTextNodes, splitStyleAttributes)
{
  var cs = serializeTreeAsScript(root, splitTextNodes, splitStyleAttributes);
  var c;
  for (var i = 0; (c = cs[i]); ++i) {
    dumpln(fuzzRecord(oPrefix2, 0, "fun: function() { " + c + " }"));
  }
  //dumpln(fuzzRecord(oPrefix2, 0, "rest: true"));
  //dumpln(fuzzRecord(oPrefix2, 0, "fun: function() { document.documentElement.offsetHeight; }"));
}

// Walks the tree in document order, not in o[...] order, mostly
// because we want it to work after the DOM has been modified heavily.
// This means it will fail for weird DOMs involving XBL or frames,
// for example.

// XXX do something about CSS @import with relative URLs (as used by wikipedia)
// (add a base href?)

function serializeTreeAsScript(root, splitTextNodes, splitStyleAttributes)
{
  function warn(s) {
    dumpln(s);
  }

  var rootStr = null;
  var magic = false;

  if (root == null) {
    root = document.documentElement;
    rootStr = "document.documentElement";
    magic = true;
  } else if (typeof root == "string") {
    // in case the page redefined eval, clobber. amazingly, this "works".
    if (typeof eval != "function")
      delete window.eval;
    rootStr = root;
    root = eval(root);
  }

  var cs = [];
  var createRoot = !magic;

  if (magic) {
    // Clear out the DOM.
    cs.push("var root = " + rootStr + "; while(root.firstChild) { root.removeChild(root.firstChild); }");

    if (root == document.documentElement) {
      cs.push(ensureIndexed(document.documentElement) + " = document.documentElement;");
    } else if (root == null) {
      cs.push("document.removeChild(document.documentElement);");
    } else {
      warn("Missing root!?");
      createRoot = true;
    }

    cs.push("/* DD" + "BEGIN */");
  }

  if (root) {
    serializeSubtreeAsScript(root, "null /* root has no ancestor chain! */", rootStr, true, createRoot);
  }

  if (magic) {
    // Look for additional disconnected subtrees in o.
    // XXX Maybe it should crawl up the parentNode chain all
    // the way to the document or document fragment, and serialize *that*.
    for (var i = 0; i < o.length; ++i) {
      var n = o[i];
      if (n && n instanceof Node && n != document && n != root) {
        if (!n.parentNode) {
          cs.push("/* o[" + i + "] has no parent (disconnected) */");
          serializeSubtreeAsScript(n, "null", "o[" + i + "]", true, true);
        } else if (n.parentNode.nodeType == 11) {
          cs.push("/* o[" + i + "] has a document fragment as its parent */");
          serializeSubtreeAsScript(n, "null", "o[" + i + "]", true, true);
        } else if (n.parentNode.nodeType == 9) {
          // Covered better by case 9 below, assuming the document is indexed
          //cs.push("/* o[" + i + "] has a document as its parent */");
          //serializeSubtreeAsScript(n, "null", "o[" + i + "]", true, true);
        }
      }
    }

    // Add selections
    var sel = window.getSelection();
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

  /*
  // Untested
  var rootix = Things.findIndex(root);
  if (rootix > 0)
    cs.push("o[" + rootix + "] = " + rootStr);
  */

  return cs;

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
      warn("serializeDOMAsScript indexed a " + description + " as o[" + ix + "].");
    }
    return "o[" + ix + "]";
  }

  // No return value; side effect is to push commands into |cs| in its closure.
  function serializeText(nodeStr, funName, text)
  {
    // Try to keep "document.write" in inline-script from being preserved,
    // because document.write blows away the document in other contexts.
    text = text.replace(/document\.write/g, "tnemucod.write");

    if (!splitTextNodes) {
      cs.push(nodeStr + " = document." + funName + "(" + simpleSource(text) + ");");
    } else {
      cs.push(nodeStr + " = document." + funName + "(\"\");");
      for (var i = 0; i < text.length; ++i) {
        cs.push(nodeStr + ".data += " + simpleSource(text[i]) + ";");
      }
    }
  }

  // No return value; side effect is to push commands into |cs| in its closure.
  function serializeSubtreeAsScript(n, ancestryPathStr, rootStr, isRoot, createRoot)
  {
    var i, a, c;

    var nodeStr = (isRoot && !createRoot && rootStr) ? rootStr : ensureIndexed(n);
    if (!nodeStr) {
      return;
    }
    if (createRoot)
      ancestryPathStr = nodeStr;

    switch (n.nodeType) {
      case 1:

        // Creating the element.
        if (!isRoot || createRoot) {
          if (n.namespaceURI) {
            // We use localName instead of tagName because the capitalization for HTML is correct.  But this throws away the XML prefix :(
            cs.push(nodeStr + " = document.createElementNS(" + simpleSource(n.namespaceURI) + ", " + simpleSource(n.localName)  + ");");
          } else {
            // In old versions of Gecko (and possibly in other older browsers), only createElement can create working HTML elements. (See bug 393340.)
            cs.push(nodeStr + " = document.createElement(" + simpleSource(n.tagName).toLowerCase() + ");");
          }
        }

        // Adding each of the element's attributes.
        var nodeIsSVG = (n.namespaceURI == "http://www.w3.org/2000/svg");
        for (i = 0; (a = n.attributes[i]); i++) {
          if (a.namespaceURI != "http://www.w3.org/2000/xmlns/") {
            if (splitStyleAttributes && a.name == "style" && n.style) {
              for (var prop, j = 0; (prop = n.style.item(j)); ++j) {
                var value = n.style.getPropertyValue(prop);
                var priority = n.style.getPropertyPriority(prop);

                // This should be a more precise regexp so it doesn't catch things like "inline-box"
                if (value.indexOf("e+") != -1 || value.indexOf("e-") != -1) {
                  warn("A style property has exponential notation (bug 373875), " + value);
                }

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

        // Adding each of the element's children (recurse).
        var newAncestryPathStr = isRoot ? (nodeStr) : (nodeStr + " || " + ancestryPathStr);

        for (i = 0; (c = n.childNodes[i]); ++i) {
          serializeSubtreeAsScript(c, newAncestryPathStr, null, false, false);
        }

        break;

      case 8:
        cs.push(nodeStr + " = document.createComment(" + simpleSource(n.data) + ");");
        break;

      case 3:
        serializeText(nodeStr, "createTextNode", n.data);
        break;

      case 4:
        serializeText(nodeStr, "createCDATASection", n.data);
        break;

      case 9:
        cs.push(nodeStr + " = document.implementation.createDocument('', '', null);");
        var newAncestryPathStr = isRoot ? (rootStr) : (nodeStr + " || " + ancestryPathStr);
        for (i = 0; (c = n.childNodes[i]); ++i) {
          serializeSubtreeAsScript(c, newAncestryPathStr, null, false, false);
        }
        break;

      default:
        warn("serializeDOMAsScript: " + nodeStr + " has unrecognized node type " + n.nodeType + ".");
    }

    // Finally, add this node to its parent (or closest surviving ancestor).
    // Using the closest surviving ancestor helps reduction.
    if (!isRoot)
      cs.push("(" + ancestryPathStr + ").appendChild(" + nodeStr + ");");
  }
}


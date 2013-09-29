function addDOMNodes(n, enterIFrames, enterSVG, enterXBL) {
  var i,c;

  if (n.getAttribute && n.getAttribute("fuzzskip")) {
    // e.g. for adding a base href tag
    return;
  }

  if (n.tagName && n.tagName.toLowerCase().indexOf("script" != -1) && n.getAttribute("id") && n.getAttribute("id").indexOf("fuzz") != -1) {
    if (n.previousSibling && n.previousSibling.nodeType == 3)
      dumpln("Warning: fuzz script found with a text (whitespace?) node before it.  This could affect node counts.");
    return;
  }

  // Add this node
  all.nodes.push(n);

  // Look for children
  for (i=0; (c = n.childNodes[i]); ++i) {
    //try {
      addDOMNodes(c, enterIFrames, enterSVG, enterXBL);
    //} catch(e) { /* Why would this fail? */ }
  }

  // If this is a frame, look inside it.
  if(enterIFrames) {
    try {
      if(n.contentDocument)
        try {
          addDOMNodes(n.contentDocument.documentElement, enterIFrames, enterSVG, enterXBL);
        } catch(ex) { /* third-party iframe */ }
    } catch(ex) { /* avoid bug 209701 (see bug 310994 which is marked as a dup) */ }
  }

  // If this is an <embed> referencing an SVG image, look inside it for SVG nodes.
  if (enterSVG) {
    if (n.getSVGDocument) {
      try{
        if (n.getSVGDocument())
          addDOMNodes(n.getSVGDocument(), enterIFrames, enterSVG, enterXBL);
      } catch(ex) { }
    }
  }

  // Look for anonymous children (XBL, at least)
  // try/catch in case browser doesn't support getAnonymousNodes, or in case Firefox decides to throw a FAILURE error (!?).
  if (enterXBL) {
    try {
      if (n.nodeType==1 && document.getAnonymousNodes(n)) {
        for(i=0; (c = document.getAnonymousNodes(n)[i]); ++i) {
          addDOMNodes(c, enterIFrames, enterSVG, enterXBL);
        }
      }
    } catch (ex) { }
  }
}

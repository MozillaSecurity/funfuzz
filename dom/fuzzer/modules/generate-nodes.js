function eaCommandMaker(namespaceURI, tagToAttrs, attrToValueRT, commonAttributes)
{
  var allTags = getKeysFromHash(tagToAttrs); // array of tags
  var allBasicAttrs = getKeysFromHash(attrToValueRT); // array of attributes

  // For exhaustive testing:
  //dumpln(uneval(allTags));

  function totallyRandomAttr()
  {
    return Random.index(rnd(2) ? allBasicAttrs : commonAttributes);
  }

  function makeSetAttribute(tag)
  {
    var attr; // a string or [string, value-generator] pair
    var vg; // a thing that can be passed to Random.pick to get a value string or number out
    var value; // a string or number

    // Sometimes, pretend it's a different tag.
    // This lets us get at tag-specific values!
    if (rnd(30) === 0) {
      tag = Random.index(allTags);
      // dumpln("Pretending it's a: " + tag);
    }
    if (rnd(30) === 0) {
      tag = "randomness"; // ;)
    }

    // Generate <audio> and <video> less frequently on old versions (see bug 623444, see bug 643171, see bug 592833)
    if (navigator.product == "Gecko" && parseInt(navigator.productSub, 10) < 16 && rnd(30) !== 0) {
      if (tag == "audio" || tag == "video") {
        tag = "randomness";
      }
    }

    // This typeof thing is because if the tag name is "filter", and you look in the MathML tag array, you could get an array extra (argh!) (does that make sense?) (array/hash confusion?)
    if ((typeof tagToAttrs[tag] == "object") && (tagToAttrs[tag].length) && (rnd(10) !== 0)) {
      attr = Random.index(tagToAttrs[tag]);
    } else {
      attr = totallyRandomAttr();
    }

    if (typeof attr == "string") {
      vg = attrToValueRT[attr];
      if (vg === null || vg === undefined) {
        dumpln("Eep, I know " + namespaceURI + " '" + tag + "' has an attribute '" + attr + "' but I don't know values for that attribute.");
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
      var otherAttr = Random.index(allBasicAttrs);
      dumpln("Using a '" + otherAttr + "' value for '" + attr + "'.");
      value = Random.pick(attrToValueRT[otherAttr]);
    }

    if (rnd(30) === 0)
      value = Random.pick(fuzzValues.texts);

    var quotedValue = simpleSource(value);

    if (rnd(2) === 1)
      // Set it as a property instead of as an attribute
      return "['" + attr + "'] = "  + quotedValue + "; ";
    else if (attr == "xlink:href")
      return ".setAttributeNS('http://www.w3.org/1999/xlink', 'xlink:href', " + quotedValue + "); ";
    else
      return ".setAttribute(" + simpleSource(attr) + ", " + quotedValue + "); ";
  }


  function makeCommand()
  {
    while(1) {
      var n1index = Things.instanceIndex("Element");
      if (n1index === -1)
        return [];
      var commandn1 = "o[" + n1index + "]";
      var n1 = o[n1index];

      switch (rnd(5)) {
      case 0:
      case 1:
      case 2:

        // Change an attribute on n1, based on n1's tagName.

        if (n1.tagName)
          return (commandn1 + makeSetAttribute(n1.tagName));
        else
          break;

      case 3:

        // Remove an attribute on n1, based on n1's current attribute list.
        var attrs = n1.attributes;
        if (attrs && attrs.length) {
          var attr = Random.index(attrs);
          if (attr)
            return commandn1 + ".removeAttribute(" + simpleSource(attr.name) + ");";
          else
            return []; // Opera bug?
        }

        break;

      case 4:

        // Create a new element!
        // Maybe put some attributes on it!
        // Place it randomly, but only rarely place it outside of the document, because that's usually boring.

        var tag = Random.index(allTags);
        var newb = Things.reserve();
        var commands = [];

        // Create the element.
        // Sometimes use uppercase tag names and/or no namespace.
        // (Suggested by Jonas Sicking.)
        switch(rnd(20))
        {
        case 0:
          commands.push(newb + " = document.createElementNS('bar', '" + tag + "');");
          break;
        case 1:
          commands.push(newb + " = document.createElement('" + tag.toUpperCase() + "');");
          break;
        case 2:
          commands.push(newb + " = document.createElement('" + tag + "');");
          break;
        case 3:
          commands.push(newb + " = document.createElementNS(" + simpleSource(namespaceURI) + ", '" + tag.toUpperCase() + "');");
          break;
        default:
          commands.push(newb + " = document.createElementNS(" + simpleSource(namespaceURI) + ", '" + tag + "');");
        }

        while (rnd(3)) {
          commands.push(newb + makeSetAttribute(tag, tagToAttrs, attrToValueRT, commonAttributes));
        }

/*
xxx ressurect the svg everything-has-a-good-id thing
          attrlist = tagToAttrs[tag];
          for (i=0;attr=attrlist[i];++i) {
            if (rnd(10) === 1 || attr[0] == "id") { // the latter part means attr is pair AND first element of pair is "id"!!  (just for SVG)
              commands.push(newb + makeSetAttribute(attr));
            }
          }
        }
*/

        if (namespaceURI == "http://www.w3.org/2000/svg" && (tag == "text" || tag == "tspan" || tag == "textPath")) {
          if (rnd(5) !== 1)
            commands.push(newb + ".appendChild(document.createTextNode(" + simpleSource(Random.pick(fuzzValues.texts)) + "));");
        }

        commands.push(commandn1 + ".appendChild(" + newb + ");");

        return commands;
      }
    }
  }

  return makeCommand;
}

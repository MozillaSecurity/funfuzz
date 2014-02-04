// https://developer.mozilla.org/en-US/docs/Web/API/URLUtils

var fuzzerURLObjects = (function() {

  var hostnames = ["mozilla.org", "www.mozilla.org", "ftp.mozilla.org"];
  var ports = [
    "80",  // http
    "443", // https
    "21",  // ftp
    "23",  // telnet - blocked - "This address uses a network port which is normally used for purposes other than Web browsing."
    "9310" // other
  ];

  var fields = [
    { field: "href",     values: fuzzValues.URIs },
    { field: "protocol", values: ["http:", "https:", "ftp:", "telnet:", "chrome:", "resource:"] },
    { field: "hostname", values: hostnames },
    { field: "origin",   values: "" }, // should be read-only
    { field: "port",     values: [ports, ""] },
    { field: "host",     values: function() { return Random.index(hostnames) + (rnd(2) ? ":"+Random.index(ports) : ""); } },
    { field: "pathname", values: ["/", "/index.html",        function() { return "/" + Random.pick(fuzzValues.texts) }] },
    { field: "search",   values: ["", "?", "?foo=bar",       function() { return "?" + Random.pick(fuzzValues.texts) }] },
    { field: "hash",     values: ["", "#", "#main-content",  function() { return "#" + Random.pick(fuzzValues.texts) }] },
    { field: "username", values: ["", fuzzValues.texts] },
    { field: "password", values: ["", fuzzValues.texts] },
  ];

  function makeCommand()
  {
    if (rnd(20) == 0) {
      return makeURLObject();
    }

    var obj = Things.instanceAny(["Location", "URL", "HTMLAnchorElement", "HTMLAreaElement"])
    if (!obj) {
      return makeURLObject();
    }

    var i = rnd(fields.length);
    if (rnd(10) == 0) {
      return obj + "." + fields[i].field + ";"; // just read the field
    }
    var j = rnd(10) ? i : rnd(fields.length); // generate a value, usually for the correct field
    return obj + "." + fields[i].field + " = " + simpleSource(Random.pick(fields[j].values)) + ";"
  }

  function makeURLObject()
  {
    switch(rnd(5)) {
      case 0:
        return Things.add('new URL(' + simpleSource(Random.pick(fuzzValues.URIs)) + ')')
      case 1:
        return Things.add('document.createElementNS("http://www.w3.org/1999/xhtml", "a")');
      case 2:
        return Things.add('document.createElementNS("http://www.w3.org/1999/xhtml", "area")');
      case 3:
        // It is safe to play with a frame's location.
        var frame = Things.instanceAny(["HTMLFrameElement", "HTMLIFrameElement"]);
        if (frame) {
          return Things.add(frame + ".location");
        }
      default:
        // It may be self-destructive to play with this document's location.
        if (rnd(100) == 0) {
          return "/*selfdestruct*/ " + Things.add("location");
        }
        return [];
    }
  }

  return { makeCommand: makeCommand };
})();

// Like SpiderMonkey's uneval, but cross-browser, and only for strings
// and simple things like numbers.
// Also escape HTML close-script tags and XML close-CDATA markers, which is a little hacky, but whatever.
function simpleSource(s)
{
  function escapeString(s)
  {
    return ("\"" +
      s.replace(/\\/g, "\\\\")
       .replace(/\"/g, "\\\"")
       .replace(/\0/g, "\\0")
       .replace(/\n/g, "\\n") +
       "\"");
  }

  var r;
  if (typeof s == "string") {
    if (/^[\n\x20-\x7f]*$/.exec(s) || !window.uneval) {
      // Printable ASCII characters and line breaks: try to make it pretty.
      r = escapeString(s);
    } else {
      // Non-ASCII: use uneval to get \u escapes.
      r = uneval(s);
    }
    r = r.replace(/<\//g, "<\\/"); // HTML close-script tags
    r = r.replace(/\]\]\>/g, "]]\\>"); // XML close-CDATA markers
    return r;
  } else {
    // For other things (such as numbers, |null|, and |undefined|), just coerce to string.
    return "" + s;
  }
}


// dumpln(simpleSource("foo\nbar"));
// dumpln(simpleSource("foo\"bar"));
// dumpln(simpleSource("foo\0bar"));
// dumpln(simpleSource("foo\xa0bar"));


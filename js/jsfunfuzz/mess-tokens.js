// Each input to |cat| should be a token or so, OR a bigger logical piece (such as a call to makeExpr).  Smaller than a token is ok too ;)

// When "torture" is true, it may do any of the following:
// * skip a token
// * skip all the tokens to the left
// * skip all the tokens to the right
// * insert unterminated comments
// * insert line breaks
// * insert entire expressions
// * insert any token

// Even when not in "torture" mode, it may sneak in extra line breaks.

// Why did I decide to toString at every step, instead of making larger and larger arrays (or more and more deeply nested arrays?).  no particular reason.

function cat(toks)
{
  if (rnd(1700) === 0)
    return totallyRandom(2, []);

  var torture = (rnd(1700) === 57);
  if (torture)
    dumpln("Torture!!!");

  var s = maybeLineBreak();
  for (var i = 0; i < toks.length; ++i) {

    // Catch bugs in the fuzzer.  An easy mistake is
    //   return /*foo*/ + ...
    // instead of
    //   return "/*foo*/" + ...
    // Unary plus in the first one coerces the string that follows to number!
    if (typeof(toks[i]) != "string") {
      dumpln("Strange item in the array passed to cat: toks[" + i + "] == " + typeof(toks[i]));
      dumpln(cat.caller);
      dumpln(cat.caller.caller);
      dumpln("Strange item in the array passed to cat: toks[" + i + "] == " + typeof(toks[i]));
    }

    if (!(torture && rnd(12) === 0))
      s += toks[i];

    s += maybeLineBreak();

    if (torture) switch(rnd(120)) {
      case 0:
      case 1:
      case 2:
      case 3:
      case 4:
        s += maybeSpace() + totallyRandom(2, []) + maybeSpace();
        break;
      case 5:
        s = "(" + s + ")"; // randomly parenthesize some *prefix* of it.
        break;
      case 6:
        s = ""; // throw away everything before this point
        break;
      case 7:
        return s; // throw away everything after this point
      case 8:
        s += UNTERMINATED_COMMENT;
        break;
      case 9:
        s += UNTERMINATED_STRING_LITERAL;
        break;
      case 10:
        if (rnd(2))
          s += "(";
        s += UNTERMINATED_REGEXP_LITERAL;
        break;
      default:
    }

  }

  return s;
}

// For reference and debugging.
/*
function catNice(toks)
{
  var s = ""
  var i;
  for (i=0; i<toks.length; ++i) {
    if(typeof(toks[i]) != "string")
      confused("Strange toks[i]: " + toks[i]);

    s += toks[i];
  }

  return s;
}
*/


var UNTERMINATED_COMMENT = "/*"; /* this comment is here so my text editor won't get confused */
var UNTERMINATED_STRING_LITERAL = "'";
var UNTERMINATED_REGEXP_LITERAL = "/";

function maybeLineBreak()
{
  if (rnd(900) === 3)
    return Random.index(["\r", "\n", "//h\n", "/*\n*/"]); // line break to trigger semicolon insertion and stuff
  else if (rnd(400) === 3)
    return rnd(2) ? "\u000C" : "\t"; // weird space-like characters
  else
    return "";
}

function maybeSpace()
{
  if (rnd(2) === 0)
    return " ";
  else
    return "";
}

function stripSemicolon(c)
{
  var len = c.length;
  if (c.charAt(len - 1) == ";")
    return c.substr(0, len - 1);
  else
    return c;
}



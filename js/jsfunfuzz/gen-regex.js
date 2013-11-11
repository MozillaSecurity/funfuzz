
/*********************************
 * GENERATING REGEXPS AND INPUTS *
 *********************************/

// The basic data structure returned by most of the regex* functions is a tuple:
//   [ regex string, array of potential matches ]
// For example:
//   ["a|b*", ["a", "b", "bbbb", "", "c"]]
// These functions work together recursively to build up a regular expression
// along with input strings.

// This paradigm works well for the recursive nature of most regular expression components,
// but breaks down when we encounter lookahead assertions or backrefs (\1).

// How many potential matches to create per regexp
var POTENTIAL_MATCHES = 10;

// Stored captures
var backrefHack = [];
for (var i = 0; i < POTENTIAL_MATCHES; ++i)
  backrefHack[i] = "";

function regexPattern(depth, parentWasQuantifier)
{
  if (depth == 0 || (rnd(depth) == 0))
    return regexTerm();

  var dr = depth - 1;

  var index = rnd(regexMakers.length);
  if (parentWasQuantifier && rnd(30)) index = rnd(regexMakers.length - 1) + 1; // avoid double quantifiers
  return (Random.index(regexMakers[index]))(dr);
}

var regexMakers =
[
  [
    // Quantifiers
    function(dr) { return regexQuantified(dr, "+", 1, rnd(10)); },
    function(dr) { return regexQuantified(dr, "*", 0, rnd(10)); },
    function(dr) { return regexQuantified(dr, "?", 0, 1); },
    function(dr) { return regexQuantified(dr, "+?", 1, 1); },
    function(dr) { return regexQuantified(dr, "*?", 0, 1); },
    function(dr) { var x = rnd(5); return regexQuantified(dr, "{" + x + "}", x, x); },
    function(dr) { var x = rnd(5); return regexQuantified(dr, "{" + x + ",}", x, x + rnd(10)); },
    function(dr) { var min = rnd(5); var max = min + rnd(5); return regexQuantified(dr, "{" + min + "," + max + "}", min, max); }
  ],
  [
    // Combinations: concatenation, disjunction
    function(dr) { return regexConcatenation(dr); },
    function(dr) { return regexDisjunction(dr); }
  ],
  [
    // Grouping
    function(dr) { return ["\\" + (rnd(3) + 1), backrefHack.slice(0)]; }, // backref
    function(dr) { return regexGrouped("(", dr, ")");   }, // capturing: feeds \1 and exec() result
    function(dr) { return regexGrouped("(?:", dr, ")"); }, // non-capturing
    function(dr) { return regexGrouped("(?=", dr, ")"); }, // lookahead
    function(dr) { return regexGrouped("(?!", dr, ")"); }  // lookahead(not)
  ]
];


function quantifierHelper(pm, min, max, pms)
{
  var actualMin = min + rnd(5) - 2;
  if (actualMin < 0 || rnd(100) < 10) actualMin = 0;

  var actualMax = max + rnd(5) - 2;
  if (actualMax < 0 || rnd(100) < 10)
  {
    actualMax = 0;
    actualMin = 0;
  }

  var repeats = min + rnd(max - min + 5) - 2;
  var returnValue = "";
  for (var i = 0; i < repeats; i++)
  {
    if (rnd(100) < 80)
      returnValue = returnValue + pm;
    else
      returnValue = returnValue + Random.index(pms);
  }
  return returnValue;
}

function regexQuantified(dr, operator, min, max)
{
  var [re, pms] = regexPattern(dr, true);
  var newpms = [];
  for (var i = 0; i < POTENTIAL_MATCHES; i++)
    newpms[i] = quantifierHelper(pms[i], min, max, pms);
  return [re + operator, newpms];
}


function regexConcatenation(dr)
{
  var [re1, strings1] = regexPattern(dr, false);
  var [re2, strings2] = regexPattern(dr, false);
  var newStrings = [];

  for (var i = 0; i < POTENTIAL_MATCHES; i++)
  {
    var chance = rnd(100);
    if (chance < 10)
      newStrings[i] = "";
    else if (chance < 20)
      newStrings[i] = strings1[i];
    else if (chance < 30)
      newStrings[i] = strings2[i];
    else if (chance < 65)
      newStrings[i] = strings1[i] + strings2[i];
    else
      newStrings[i] = Random.index(strings1) + Random.index(strings2);
  }

  return [re1 + re2, newStrings];
}

function regexDisjunction(dr)
{
  var [re1, strings1] = regexPattern(dr, false);
  var [re2, strings2] = regexPattern(dr, false);
  var newStrings = [];

  for (var i = 0; i < POTENTIAL_MATCHES; i++)
  {
    var chance = rnd(100);
    if (chance < 10)
      newStrings[i] = "";
    else if (chance < 20)
      newStrings[i] = Random.index(strings1) + Random.index(strings2);
    else if (chance < 60)
      newStrings[i] = strings1[i];
    else
      newStrings[i] = strings2[i];
  }
  return [re1 + "|" + re2, newStrings];
}

function regexGrouped(prefix, dr, postfix)
{
  var [re, strings] = regexPattern(dr, false);
  var newStrings = [];
  for (var i = 0; i < POTENTIAL_MATCHES; ++i) {
    newStrings[i] = rnd(5) ? strings[i] : "";
    if (prefix == "(" && strings[i].length < 40 && rnd(3) === 0) {
      backrefHack[i] = strings[i];
    }
  }
  return [prefix + re + postfix, newStrings];
}


var letters =
["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
 "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"];

var hexDigits = [
  "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
  "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
  "a", "b", "c", "d", "e", "f",
  "A", "B", "C", "D", "E", "F"
];

function regexTerm()
{
  var [re, oneString] = regexTermPair();
  var strings = [];
  for (var i = 0; i < POTENTIAL_MATCHES; ++i) {
    strings[i] = rnd(5) ? oneString : regexTermPair()[1];
  }
  return [re, strings];
}

function regexTermPair()
{
  if (rnd(8)) {
    var cc1 = 32 + rnd(128-32);
    //var cc2 = String.fromCharCode(
    var c1 = String.fromCharCode(cc1);
    var c2 = rnd(10) ? c1 : rnd(2) ? c1.toLowerCase() : c1.toUpperCase();
    return [c1, c2];
  }

  var y = [
    function(dr) { var index = rnd(26); return ["\\c" + letters[index], String.fromCharCode(index+1)]; },
    function(dr) { var hexDigs = Random.index(hexDigits) + Random.index(hexDigits); return ["\\u00" + hexDigs, String.fromCharCode(parseInt(hexDigs, 16))]; },
    function(dr) { var hexDigs = Random.index(hexDigits) + Random.index(hexDigits); return ["\\x" + hexDigs, String.fromCharCode(parseInt(hexDigs, 16))]; },
    function(dr) { var hexDigs = Random.index(hexDigits) + Random.index(hexDigits) + Random.index(hexDigits) + Random.index(hexDigits); return ["\\u" + hexDigs, String.fromCharCode(parseInt(hexDigs, 16))]; },
    function(dr) { var chr = String.fromCharCode(rnd(256)); return [chr, chr]; },
    function(dr) { var chr = String.fromCharCode(rnd(65536)); return [chr, chr]; },
    function(dr) { var octal = String.fromCharCode(rnd(256)); return ["\\" + octal, String.fromCharCode(parseInt(octal, 8))]; },
    function(dr) { var pair = regexCharacterClassData(dr, true); return ["[" + pair[0] + "]", pair[1] ]; },
    function(dr) { var pair = regexCharacterClassData(dr, false); return ["[^" + pair[0] + "]", pair[1] ]; },
    function(dr) { return [".", String.fromCharCode(rnd(65536))]; },
    function(dr) { return Random.index([ ["[\\b]", "\b"], ["\\", "\\"], ["\\\\", "\\"], ["\\\\\\\\", "\\\\"], ["\"", "\""], ["\\\"", "\""], ["\[", "["], ["\]", "]"], ["\(", "("], ["\)", ")"], ["\}", "}"], ["\{", "{"], ["\|", "|"], ["\+", "+"], ["\*", "*"], ["\?", "?"], ["\:", ":"], ["\=", "="], ["\\0" /* regexp match null */, "\0" /* actual null */], ["\0", "\0"], ["%n", "%n"], ["\\n", "\n"] ]); },
    function(dr) { var term = Random.index(["\\1", "\\2", "\\3", "\\4", "\\5", "\\10"]); return [term, regexTermPair()[1] ]; }, // reference other parts of regexp
    function(dr) { var term = Random.index(["^", "$", ]); return [term, ""]; }, // beginning or end of string
    function(dr) { var term = Random.index(["\\b", "\\B", "\\d", "\\D", "\\s", "\\S", "\\w", "\\W", "\\f", "\\t"]); return [term, regexTermPair()[1] ]; }, // words, boundaries, etc.
  ];

  var term = Random.index(y)();

  return term;

}

function regexCharacterClassData(dr, inRange)
{
  if (dr < 0)
    return "";

  var y = [
    function(dr) { var start = rnd(256); var end = rnd(256); if (end < start) { var tmp = start ; start = end ; end = tmp; } var middle; if (inRange) middle = rnd(start - end) + start; else middle = rnd(start); return [String.fromCharCode(start) + "-" + String.fromCharCode(end), String.fromCharCode(middle)]; },
    function(dr) { var start = rnd(65536); var end = rnd(65536); if (end < start) { var tmp = start ; start = end ; end = tmp; } var middle; if (inRange) middle = rnd(start - end) + start; else middle = rnd(start); return [String.fromCharCode(start) + "-" + String.fromCharCode(end), String.fromCharCode(middle)]; },
    function(dr) { var start = rnd(256); var end = rnd(65536); if (end < start) { var tmp = start ; start = end ; end = tmp; } var middle; if (inRange) middle = rnd(start - end) + start; else middle = rnd(start); return [String.fromCharCode(start) + "-" + String.fromCharCode(end), String.fromCharCode(middle)]; },
    function(dr) { var pair1 = regexTermPair(); var pair2 = regexTermPair(); return [ pair1[0] + "-" + pair2[0], pair1[1] ]; },
    function(dr) { var pair1 = regexTermPair(); var pair2 = regexTermPair(); return [ pair1[0] + "-" + pair2[0], pair2[1] ]; },
    function(dr) { return regexTermPair(); },
    function(dr) { var pair1 = regexCharacterClassData(dr-1, inRange); var pair2 = regexCharacterClassData(dr-1, inRange); return [ pair1[0] + pair2[0], pair1[1] ]; },
    function(dr) { var pair1 = regexCharacterClassData(dr-1, inRange); var pair2 = regexCharacterClassData(dr-1, inRange); return [ pair1[0] + pair2[0], pair2[1] ]; }
  ];

  return (Random.index(y))();
}


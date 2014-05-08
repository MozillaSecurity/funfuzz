
/*********************************
 * GENERATING REGEXPS AND INPUTS *
 *********************************/

// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/RegExp
// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_Expressions

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
for (var i = 0; i < POTENTIAL_MATCHES; ++i) {
  backrefHack[i] = "";
}

function regexNumberOfMatches()
{
  if (rnd(10))
    return rnd(5);
  return Math.pow(2, rnd(40)) + rnd(3) - 1;
}

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
    function(dr) { var x = regexNumberOfMatches(); return regexQuantified(dr, "{" + x + "}", x, x); },
    function(dr) { var x = regexNumberOfMatches(); return regexQuantified(dr, "{" + x + ",}", x, x + rnd(10)); },
    function(dr) { var min = regexNumberOfMatches(); var max = min + regexNumberOfMatches(); return regexQuantified(dr, "{" + min + "," + max + "}", min, max); }
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
  var repeats = Math.min(min + rnd(max - min + 5) - 2, 10);
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

function regexCharCode()
{
  return rnd(2) ? rnd(256) : rnd(65536);
}

// These return matching pairs: [regex fragment, charcode for a matching one-character string].
var regexCharacterMakers = Random.weighted([
  // Possibly incorrect
  { w:20, v: function() { var cc = regexCharCode(); return [       String.fromCharCode(cc), cc]; } }, // literal that doesn't need to be escaped (OR wrong)
  { w: 4, v: function() { var cc = regexCharCode(); return ["\\" + String.fromCharCode(cc), cc]; } }, // escaped special character OR unnecessary escape (OR wrong)
  { w: 1, v: function() { return ["\\0",  0]; } },  // null [ignoring the "do not follow this with another digit" rule which would turn it into an octal escape]
  { w: 1, v: function() { return ["\\B", 66]; } },  // literal B -- ONLY within a character class. (Elsewhere, it's a "zero-width non-word boundary".)
  { w: 1, v: function() { return ["\\b",  8]; } },  // backspace -- ONLY within a character class. (Elsewhere, it's a "zero-width word boundary".)

  // Correct, unless I screwed up
  { w: 1, v: function() { return ["\\t",  9]; } },  // tab
  { w: 1, v: function() { return ["\\n", 10]; } },  // line break
  { w: 1, v: function() { return ["\\v", 11]; } },  // vertical tab
  { w: 1, v: function() { return ["\\f", 12]; } },  // form feed
  { w: 1, v: function() { return ["\\r", 13]; } },  // carriage return
  { w: 5, v: function() { var controlCharacterCode = rnd(26) + 1; return ["\\c" + String.fromCharCode(64 + controlCharacterCode), controlCharacterCode]; } },
  //{ w: 5, v: function() { var cc = regexCharCode(); return ["\\0" + cc.toString(8), cc] } }, // octal escape
  { w: 5, v: function() { var twoHex = Random.index(hexDigits) + Random.index(hexDigits); return ["\\x" + twoHex, parseInt(twoHex, 16)]; } },
  { w: 5, v: function() { var twoHex = Random.index(hexDigits) + Random.index(hexDigits); return ["\\u00" + twoHex, parseInt(twoHex, 16)]; } },
  { w: 5, v: function() { var fourHex = Random.index(hexDigits) + Random.index(hexDigits) + Random.index(hexDigits) + Random.index(hexDigits); return ["\\u" + fourHex, parseInt(fourHex, 16)]; } },
]);

function regexCharacter()
{
  var [matcher, charcode] = Random.index(regexCharacterMakers)();
  switch(rnd(10)) {
    case 0:  return [matcher, charcode + 32]; // lowercase
    case 1:  return [matcher, charcode - 32]; // uppercase
    case 2:  return [matcher, regexCharCode()]; // some other character
    default: return [matcher, charcode];
  }
}


var regexBuiltInCharClasses = [
    "\\d", "\\D", // digit
    "\\s", "\\S", // space
    "\\w", "\\W", // "word" character (alphanumeric plus underscore)
];

// Returns POTENTIAL_MATCHES one-character strings, mostly consisting of the input characters
function regexOneCharStringsWith(frequentChars) {
  var matches = [];
  for (var i = 0; i < POTENTIAL_MATCHES; ++i) {
    matches.push(rnd(8) ? Random.index(frequentChars) : String.fromCharCode(regexCharCode()));
  }
  return matches;
}

// Returns POTENTIAL_MATCHES short strings, using the input characters a lot.
function regexShortStringsWith(frequentChars) {
  var matches = [];
  for (var i = 0; i < POTENTIAL_MATCHES; ++i) {
    var s = "";
    while (rnd(3)) {
      s += rnd(4) ? Random.index(frequentChars) : String.fromCharCode(regexCharCode());
    }
    matches.push(s);
  }
  return matches;
}

var regexTermMakers =
  [
    function() { return regexCharacterClass(); },
    function() { var [re, cc] = regexCharacter();   return [re, regexOneCharStringsWith([String.fromCharCode(cc)])]; },
    function() { return [Random.index(regexBuiltInCharClasses), regexOneCharStringsWith(["0", "a", "_"])]; },
    function() { return ["[^]",                                 regexOneCharStringsWith(["\n"])];     },
    function() { return [".",                                   regexOneCharStringsWith(["\n"])];     },
    function() { return [Random.index(["^", "$"]),              regexShortStringsWith(["\n"])];     },            // string boundaries or line boundaries (with /m)
    function() { return [Random.index(["\\b", "\\B"]),          regexShortStringsWith([" ", "\n", "a", "1"])]; }, // word boundaries
  ];

function regexTerm()
{
  return Random.index(regexTermMakers)();
}

// Returns a pair: [(regex char class), (POTENTIAL_MATCHES number of strings that might match)]
// e.g. ["[a-z0-9]", ["a", "8", ...]]
function regexCharacterClass()
{
  var ranges = rnd(5);
  var inRange = rnd(2);
  var charBucket = [String.fromCharCode(regexCharCode())]; // from which potenial matches will be drawn

  var re = "[";
  if (!inRange) {
    re += "^";
  }

  for (var i = 0; i < ranges; ++i) {
    if (rnd(100) == 0) {
      // Confuse things by tossing in an extra "-"
      re += "-";
      if (rnd(2)) {
        re += String.fromCharCode(regexCharCode())
      }
    }

    if (rnd(3) == 1) {
      // Add a built-in class, like "\d"
      re += Random.index(regexBuiltInCharClasses);
      charBucket.push("a");
      charBucket.push("0");
      charBucket.push("_");
    } else if (rnd(2)) {
      // Add a range, like "a-z"
      var a = regexCharacter();
      var b = regexCharacter();
      if ((a[1] <= b[1]) == !!rnd(10)) {
        [lo, hi] = [a, b];
      } else {
        [lo, hi] = [b, a];
      }

      re += lo[0] + "-" + hi[0];
      charBucket.push(String.fromCharCode(lo[1] + rnd(3) - 1));
      charBucket.push(String.fromCharCode(hi[1] + rnd(3) - 1));
      charBucket.push(String.fromCharCode(lo[1] + rnd(Math.max(hi[1] - lo[1], 1)))); // something in the middle
    } else {
      // Add a single character
      var a = regexCharacter();
      re += a[0];
      charBucket.push(String.fromCharCode(a[1]));
    }
  }

  re += "]"
  return [re, pickN(charBucket, POTENTIAL_MATCHES)];
}

function pickN(bucket, picks)
{
  var picked = [];
  for (var i = 0; i < picks; ++i) {
    picked.push(Random.index(bucket));
  }
  return picked;
}

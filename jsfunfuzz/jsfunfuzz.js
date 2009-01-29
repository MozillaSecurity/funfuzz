/* ***** BEGIN LICENSE BLOCK *****
 * Version: MPL 1.1/GPL 2.0/LGPL 2.1
 *
 * The contents of this file are subject to the Mozilla Public License Version
 * 1.1 (the "License"); you may not use this file except in compliance with
 * the License. You may obtain a copy of the License at
 * http://www.mozilla.org/MPL/
 *
 * Software distributed under the License is distributed on an "AS IS" basis,
 * WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
 * for the specific language governing rights and limitations under the
 * License.
 *
 * The Original Code is jsfunfuzz.
 *
 * The Initial Developer of the Original Code is
 * Jesse Ruderman.
 * Portions created by the Initial Developer are Copyright (C) 2006-2008
 * the Initial Developer. All Rights Reserved.
 *
 * Contributor(s):
 *
 * Alternatively, the contents of this file may be used under the terms of
 * either the GNU General Public License Version 2 or later (the "GPL"), or
 * the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
 * in which case the provisions of the GPL or the LGPL are applicable instead
 * of those above. If you wish to allow use of your version of this file only
 * under the terms of either the GPL or the LGPL, and not to allow others to
 * use your version of this file under the terms of the MPL, indicate your
 * decision by deleting the provisions above and replace them with the notice
 * and other provisions required by the GPL or the LGPL. If you do not delete
 * the provisions above, a recipient may use your version of this file under
 * the terms of any one of the MPL, the GPL or the LGPL.
 *
 * ***** END LICENSE BLOCK ***** */
 



/********************
 * ENGINE DETECTION *
 ********************/

// jsfunfuzz is best run in a command-line shell.  It can also run in
// a web browser, but you might have trouble reproducing bugs that way.

var ENGINE_UNKNOWN = 0;
var ENGINE_SPIDERMONKEY_TRUNK = 1;
var ENGINE_SPIDERMONKEY_MOZ_1_8 = 2;
var ENGINE_JAVASCRIPTCORE = 3;

var engine = ENGINE_UNKNOWN;
var jsshell = (typeof window == "undefined");
if (jsshell) {
  dump = print;
  dumpln = print;
  printImportant = function(s) { dumpln("***"); dumpln(s); }
  if (typeof line2pc == "function") {
    if (typeof countHeap == "function")
      engine = ENGINE_SPIDERMONKEY_TRUNK;
    else
      engine = ENGINE_SPIDERMONKEY_MOZ_1_8;
    version(180); // 170: make "yield" and "let" work. 180: sane for..in.
    options("anonfunfix");
  } else if (typeof debug == "function") {
    engine = ENGINE_JAVASCRIPTCORE;
  }
} else {
  if (navigator.userAgent.indexOf("WebKit") != -1) {
    engine = ENGINE_JAVASCRIPTCORE;
    // This worked in Safari 3.0, but it might not work in Safari 3.1.
    dump = function(s) { console.log(s); } 
  } else if (navigator.userAgent.indexOf("Gecko") != -1 && navigator.userAgent.indexOf("rv:1.8") != -1) {
    engine = ENGINE_SPIDERMONKEY_MOZ_1_8;
  } else if (navigator.userAgent.indexOf("Gecko") != -1) {
    engine = ENGINE_SPIDERMONKEY_TRUNK;
  } else if (typeof dump != "function") {
    // In other browsers, jsfunfuzz does not know how to log anything.
    dump = function() { };
  }
  dumpln = function(s) { dump(s + "\n"); }

  printImportant = function(s) { 
    dumpln(s);
    var p = document.createElement("pre");
    p.appendChild(document.createTextNode(s));
    document.body.appendChild(p);
  }
}

if (typeof gc == "undefined")
  gc = function(){};

var haveUsefulDis = typeof dis == "function" && typeof dis() == "string";

var haveE4X = (typeof XML == "function");
if (haveE4X)
  XML.ignoreComments = false; // to make uneval saner -- see bug 465908

function simpleSource(s)
{
  function hexify(c)
  {
    var code = c.charCodeAt(0);
    var hex = code.toString(16);
    while (hex.length < 4)
      hex = "0" + hex;
    return "\\u" + hex;
  }

  if (typeof s == "string")
    return "\"" + s.replace(/\\/g, "\\\\")
                   .replace(/\"/g, "\\\"")
                   .replace(/\0/g, "\\0")
                   .replace(/\n/g, "\\n")
                   .replace(/[^ -~]/g, hexify) // not space (32) through tilde (126)
                   + "\"";
  else
    return "" + s; // hope this is right ;)  should work for numbers.
}

var haveRealUneval = (typeof uneval == "function");
if (!haveRealUneval)
  uneval = simpleSource;

if (engine == ENGINE_UNKNOWN)
  printImportant("Targeting an unknown JavaScript engine!");
else if (engine == ENGINE_SPIDERMONKEY_MOZ_1_8)
  printImportant("Targeting SpiderMonkey / Gecko (Mozilla 1.8 branch).");
else if (engine == ENGINE_SPIDERMONKEY_TRUNK)
  printImportant("Targeting SpiderMonkey / Gecko (Mozilla 1.9 or trunk).");
else if (engine == ENGINE_JAVASCRIPTCORE)
  printImportant("Targeting JavaScriptCore / WebKit.");

function printAndStop(s)
{
  printImportant(s)
  if (jsshell)
    quit();
}

function errorToString(e)
{
  try {
    return ("" + e);
  } catch (e2) {
    return "Can't toString the error!!";
  }
}

var jitEnabled = (engine == ENGINE_SPIDERMONKEY_TRUNK) && jsshell && options().indexOf("jit") != -1;


/***********************
 * AVOIDING KNOWN BUGS *
 ***********************/

function whatToTestSpidermonkeyTrunk(code)
{
  return {
  
    allowParse: true,
    
    // Exclude things here if decompiling the function causes a crash.
    allowDecompile: true,
  
    // Exclude things here if decompiling returns something bogus that won't compile.
    checkRecompiling: true
      && (code.indexOf("#") == -1)                    // avoid bug 367731
      && !( code.match( /\..*\@.*(this|null|false|true).*\:\:/ ))  // avoid bug 381197
      && !( code.match( /arguments.*\:\:/ ))       // avoid bug 355506
      && !( code.match( /\:.*for.*\(.*var.*\)/ ))  // avoid bug 352921
      && !( code.match( /\:.*for.*\(.*let.*\)/ ))  // avoid bug 352921
      && !( code.match( /for.*let.*\).*function/ )) // avoid bug 352735 (more rebracing stuff)
      && !( code.match( /for.*\(.*\(.*in.*;.*;.*\)/ )) // avoid bug 353255
      && !( code.match( /while.*for.*in/ )) // avoid bug 381963
      && !( code.match( /const.*arguments/ ))        // avoid bug 355480
      && !( code.match( /var.*arguments/ ))          // avoid bug 355480
      && !( code.match( /let.*arguments/ ))          // avoid bug 355480
      && !( code.match( /let/ ))   // avoid bug 462309 :( :( :(
      ,
  
    // Exclude things here if decompiling returns something incorrect or non-canonical, but that will compile.
    checkForMismatch: true
      && !( code.match( /const.*if/ ))               // avoid bug 352985
      && !( code.match( /if.*const/ ))               // avoid bug 352985
      && !( code.match( /\{.*\}.*=.*\[.*=.*\]/ ))    // avoid bug 376558
      && !( code.match( /\[.*\].*=.*\[.*=.*\]/ ))    // avoid bug 376558
      && !( code.match( /with.*try.*function/ ))     // avoid bug 418285
      && !( code.match( /if.*try.*function/ ))       // avoid bug 418285
      && !( code.match( /\[.*\].*\=.*\[.*\,/ ))      // avoid bug 355051
      && !( code.match( /\{.*\}.*\=.*\[.*\,/ ))      // avoid bug 355051 where empty {} becomes []
      && (code.indexOf("-0") == -1)        // constant folding isn't perfect
      && (code.indexOf("-1") == -1)        // constant folding isn't perfect
      && (code.indexOf("default") == -1)   // avoid bug 355509
      && (code.indexOf("delete") == -1)    // avoid bug 352027, which won't be fixed for a while :(
      && (code.indexOf("const") == -1)     // avoid bug 352985, bug 353020, and bug 355480 :(
      && (code.indexOf("&&") == -1)        // ignore bug 461226 with a hatchet
      && (code.indexOf("||") == -1)        // ignore bug 461226 with a hatchet
      // avoid bug 352085: keep operators that coerce to number (or integer)
      // at constant-folding time (?) away from strings
      &&
           (
             (code.indexOf("\"") == -1 && code.indexOf("\'") == -1)
             ||
             (
                  (code.indexOf("%")  == -1)
               && (code.indexOf("/")  == -1)
               && (code.indexOf("*")  == -1)
               && (code.indexOf("-")  == -1)
               && (code.indexOf(">>") == -1)
               && (code.indexOf("<<") == -1)
             )
          )
      ,

    // Exclude things here if the decompilation doesn't match what the function actually does
    checkDisassembly: true
      && !( code.match( /\@.*\:\:/ )),  // avoid bug 381197 harder than above
    
    checkForExtraParens: true
      && !code.match( /\(.*for.*\(.*in.*\).*\)/ )  // ignore bug 381213, and unfortunately anything with genexps
      && !code.match( /if.*\(.*=.*\)/)      // ignore extra parens added to avoid strict warning
      && !code.match( /while.*\(.*=.*\)/)   // ignore extra parens added to avoid strict warning
      && !code.match( /\?.*\=/)             // ignore bug 475893
    ,
    
    allowExec: unlikelyToHang(code)
      && code.indexOf("for..in")  == -1 // for (x.y in x) causes infinite loops :(
      && code.indexOf("finally")  == -1 // avoid bug 380018 and bug 381107 :(
      && code.indexOf("valueOf")  == -1 // avoid bug 355829
      && code.indexOf("<>")       == -1 // avoid bug 334628, hopefully
      && (jsshell || code.indexOf("nogeckoex") == -1)
      && !( code.match( /function.*::.*=/ )) // avoid ????
      ,
  
    allowIter: true,
  
    checkUneval: true
      // exclusions won't be perfect, since functions can return things they don't
      // appear to contain, e.g. with "return x;"
      && (code.indexOf("<") == -1 || code.indexOf(".") == -1)  // avoid bug 379525
      && (code.indexOf("<>") == -1)                            // avoid bug 334628
  };
}


function whatToTestSpidermonkey18Branch(code)
{
  return {
  
    allowParse: true
      && !(code.match(/=.*#.*=/)),   // avoid bug 390231

    // Exclude things here if decompiling the function causes a crash.
    allowDecompile: true
      && !(code.match( /for.*for.*in.*in/ )),         // avoid bug 376370
  
    // Exclude things here if decompiling returns something bogus that won't compile.
    checkRecompiling: false, // on branch, only interested in crashes for now
  
    // Exclude things here if decompiling returns something incorrect or non-canonical, but that will compile.
    checkForMismatch: false,
    checkForExtraParens: false,
      
    allowExec: unlikelyToHang(code)
      && code.indexOf("for..in")  == -1 // for (x.y in x) causes infinite loops :(
      && code.indexOf("finally")  == -1 // avoid bug 380018 and bug 381107 :(
      && code.indexOf("valueOf")  == -1 // avoid bug 355829
      && code.indexOf("<>")       == -1 // avoid bug 334628, hopefully
      && (jsshell || code.indexOf("nogeckoex") == -1)
      && !( code.match( /delete.*Function/ )) // avoid bug 352604 (exclusion needed despite the realFunction stuff?!)
      && !( code.match( /function.*::.*=/ )) // avoid ????
      ,
  
    allowIter: true,
  
    checkUneval: false
  };
}


function whatToTestJavaScriptCore(code)
{
  return {
  
    allowParse: true,

    allowDecompile: true,

    checkRecompiling: true,
    
    checkForMismatch: true
      && !code.match( /new.*\(.*\).*\./ )      // avoid bug 17931
      && !code.match( /new.*\(.*\).*\[/ )      // avoid bug 17931
      ,

    checkForExtraParens: false, // ?

    allowExec: unlikelyToHang(code)
      && !code.match(/with.*const/)            // avoid bug 17924
      && !code.match(/catch.*const/)           // avoid bug 17924
      && !code.match(/break.*finally/)         // avoid bug 17932
      && !code.match(/continue.*finally/)      // avoid bug 17932
      ,

    allowIter: false, // JavaScriptCore does not support |yield| and |Iterator|

    checkUneval: false // JavaScriptCore does not support |uneval|

  };
}

function whatToTestGeneric(code)
{
  return {
    allowParse: true,
    allowDecompile: true,
    checkRecompiling: true,
    checkForMismatch: true,
    checkForExtraParens: false, // most js engines don't try to guarantee lack of extra parens
    allowExec: unlikelyToHang(code),
    allowIter: ("Iterator" in this),
    checkUneval: haveRealUneval
  };
}

if (engine == ENGINE_SPIDERMONKEY_TRUNK)
  whatToTest = whatToTestSpidermonkeyTrunk;
else if (engine == ENGINE_SPIDERMONKEY_MOZ_1_8)
  whatToTest = whatToTestSpidermonkey18Branch;
else if (engine == ENGINE_JAVASCRIPTCORE)
  whatToTest = whatToTestJavaScriptCore;
else
  whatToTest = whatToTestGeneric;


function unlikelyToHang(code)
{
  // Things that are likely to hang in all JavaScript engines
  return true
    && code.indexOf("infloop") == -1
    && !( code.match( /const.*for/ )) // can be an infinite loop: function() { const x = 1; for each(x in ({a1:1})) dumpln(3); }
    && !( code.match( /for.*const/ )) // can be an infinite loop: for each(x in ...); const x;
    && !( code.match( /for.*in.*uneval/ )) // can be slow to loop through the huge string uneval(this), for example
    && !( code.match( /for.*for.*for/ )) // nested for loops (including for..in, array comprehensions, etc) can take a while
    ;
}




/*************************
 * DRIVING & BASIC TESTS *
 *************************/

var allMakers = [];
function totallyRandom(depth) {
  var dr = depth + (rnd(5) - 2); // !

  return (rndElt(allMakers))(dr);
}

function init()
{
  for (var f in this)
    if (f.indexOf("make") == 0 && typeof this[f] == "function")
      allMakers.push(this[f]);
}

function start()
{
  init();
  // dumpln(uneval([f.name for each (f in allMakers)]));

  count = 0;

  if (jsshell) {
    var MAX_TOTAL_TIME = 200/* seconds */ * 1000;
    var startTime = new Date();

    do {
      testOne();
      var elapsed1 = new Date() - lastTime;
      if (elapsed1 > 1000) {
        print("That took " + elapsed1 + "ms!");
      }
      var lastTime = new Date();
    } while(lastTime - startTime < MAX_TOTAL_TIME);
    
    dumpln("It's looking good!"); // Magic string that multi_timed_run.py looks for
  } else {
    setTimeout(testStuffForAWhile, 200);
  }
}

function testStuffForAWhile()
{
  for (var j = 0; j < 100; ++j)
    testOne();

  if (count % 10000 < 100)
    printImportant("Iterations: " + count);

  setTimeout(testStuffForAWhile, 30);
}

function testOne()
{
  ++count;

  var code = makeStatement(8);
  
  // Test tracing frequently -- but not so often that jsfunfuzz slows down too much to hit interesting combinations.
  if (rnd(20) == 0)
    code = randomRepeater() + " { " + code + " } ";

//  if (rnd(10) == 1) {
//    var dp = "/*infloop-deParen*/" + rndElt(deParen(code));
//    if (dp)
//      code = dp;
//  }
  dumpln("count=" + count + "; tryItOut(" + uneval(code) + ");");

  tryItOut(code);
}

function tryItOut(code)
{
  var c; // a harmless variable for closure fun

  // Accidenally leaving gczeal enabled for a long time would make jsfunfuzz really slow.
  if ("gczeal" in this)
    gczeal(0);

  // SpiderMonkey shell does not schedule GC on its own.  Help it not use too much memory.
  if (count % 1000 == 0) {
    dumpln("Paranoid GC (count=" + count + ")!");
    realGC();
  }

  // regexps can't match across lines, so replace line breaks with spaces.
  var wtt = whatToTest(code.replace(/\n/g, " ").replace(/\r/g, " "));

  if (!wtt.allowParse)
    return;
    
  if (wtt.allowExec && count % 5 == 0) {
    try {
      print("Plain eval");
      eval(code);
    } catch(e) {
      print(errorToString(e));
    }
    tryEnsureSanity();
    return;
  }

  var f = tryCompiling(code, wtt.allowExec);

  // optionalTests(f, code, wtt);

  if (f && wtt.allowDecompile) {
    tryRoundTripStuff(f, code, wtt);
    if (0 && haveUsefulDis && wtt.checkRecompiling && wtt.checkForMismatch && wtt.checkDisassembly)
      checkRoundTripDisassembly(f, code);
  }

  var rv = null;
  if (wtt.allowExec && f) {
    rv = tryRunning(f, code);
    tryEnsureSanity();
  }
    
  if (wtt.allowIter && rv && typeof rv == "object") {
    tryIteration(rv);
    tryEnsureSanity();
  }
  
  // "checkRecompiling && checkForMismatch" here to catch returned functions
  if (wtt.checkRecompiling && wtt.checkForMismatch && wtt.checkUneval && rv && typeof rv == "object") {
    testUneval(rv);
  }
  
  if (verbose)
    dumpln("Done trying out that function!");
    
  dumpln("");
}

function tryCompiling(code, allowExec)
{
  var c; // harmless local variable for closure fun

  try {
  
    // Try two methods of creating functions, just in case there are differences.
    if (count % 2 == 0 && allowExec) {
      if (verbose)
        dumpln("About to compile, using eval hack.")
      return eval("(function(){" + code + "});"); // Disadvantage: "}" can "escape", allowing code to *execute* that we only intended to compile.  Hence the allowExec check.
    }
    else {
      if (verbose)
        dumpln("About to compile, using new Function.")
      return new Function(code);
    }
  } catch(compileError) {
    dumpln("Compiling threw: " + errorToString(compileError));
    return null;
  }
}

function tryRunning(f, code)
{
  try { 
    if (verbose)
      dumpln("About to run it!");
    var rv = f();
    if (verbose)
      dumpln("It ran!");
    return rv;
  } catch(runError) {
    if(verbose)
      dumpln("Running threw!  About to toString to error.");
    var err = errorToString(runError);
    dumpln("Running threw: " + err);
    tryEnsureSanity();
    checkErrorMessage(err, code);
    return null;
  }
}


// Store things now so we can restore sanity later.
var realEval = eval;
var realFunction = Function;
var realGC = gc;
var realUneval = uneval;
var realToString = toString;
var realToSource = this.toSource; // "this." because it only exists in spidermonkey


function tryEnsureSanity()
{
  // At least one bug in the past has put exceptions in strange places.  This also catches "eval getter" issues.
  try { eval("") } catch(e) { dumpln("That really shouldn't have thrown: " + errorToString(e)); }

  // Try to get rid of any fake 'unwatch' functions.
  delete unwatch;

  // Restore important stuff that might have been broken as soon as possible :)
  if ('unwatch' in this) {
    this.unwatch("eval")
    this.unwatch("Function")
    this.unwatch("gc")
    this.unwatch("uneval")
    this.unwatch("toSource")
    this.unwatch("toString")
  }

  if ('__defineSetter__' in this) {
    // The only way to get rid of getters/setters is to delete the property.
    delete eval;
    if (engine != ENGINE_SPIDERMONKEY_MOZ_1_8) // avoid bug 352604 on branch
      delete Function;
    delete gc;
    delete uneval;
    delete toSource;
    delete toString;
  }

  eval = realEval;
  Function = realFunction;
  gc = realGC;
  uneval = realUneval;
  toSource = realToSource;
  toString = realToString;

  // These can fail if the page creates a getter for "eval", for example.
  if (!eval)
    printImportant("WTF did my |eval| go?");
  if (eval != realEval)
    printImportant("WTF did my |eval| get replaced by?")
  if (Function != realFunction)
    printImportant("WTF did my |Function| get replaced by?")
}

function tryIteration(rv)
{
  try {
    if (!(Iterator(rv) === rv))
      return; // not an iterator
  }
  catch(e) {
    // Is it a bug that it's possible to end up here?  Probably not!
    dumpln("Error while trying to determine whether it's an iterator!");
    dumpln("The error was: " + e);
    return;
  }
  
  dumpln("It's an iterator!");
  try {
    var iterCount = 0;
    var iterValue;
    // To keep Safari-compatibility, don't use "let", "each", etc.
    for /* each */ ( /* let */ iterValue in rv)
      ++iterCount;
    dumpln("Iterating succeeded, iterCount == " + iterCount);
  } catch (iterError) {
    dumpln("Iterating threw!");
    dumpln("Iterating threw: " + errorToString(iterError));
  }
}



/***********************************
 * WHOLE-FUNCTION DECOMPILER TESTS *
 ***********************************/

function tryRoundTripStuff(f, code, wtt)
{
  if (verbose)
    dumpln("About to do the 'toString' round-trip test");

  // Functions are prettier with line breaks, so test toString before uneval.
  checkRoundTripToString(f, code, wtt); 

  if (wtt.checkRecompiling && wtt.checkForMismatch && wtt.checkForExtraParens) {
    try {
      testForExtraParens(f, code);
    } catch(e) { /* bug 355667 is annoying here too */ }
  }
  
  if (haveRealUneval) {
    if (verbose)
      dumpln("About to do the 'uneval' round-trip test");
    checkRoundTripUneval(f, code, wtt);
  }
}

// Function round-trip with implicit toString
function checkRoundTripToString(f, code, wtt)
{
  var uf, g;
  try {
    uf = "" + f;
  } catch(e) { reportRoundTripIssue("Round-trip with implicit toString: can't toString", code, null, null, errorToString(e)); return; }

  checkForCookies(uf);
  
  if (uf == "[object Function]" && engine == ENGINE_SPIDERMONKEY_MOZ_1_8) {
    print("Skipping round-trip test -- bug 432075");
    return;
  }

  if (wtt.checkRecompiling) {
    try {
      g = eval("(" + uf + ")");
      var fs = "" + f;
      var gs = "" + g;
      if (wtt.checkForMismatch && fs != gs) {
        reportRoundTripIssue("Round-trip with implicit toString", code, fs, gs, "mismatch");
        wtt.checkForMismatch = false;
      }
    } catch(e) {
      reportRoundTripIssue("Round-trip with implicit toString: error", code, f, g, errorToString(e));
    }
  }
}

// Function round-trip with uneval
function checkRoundTripUneval(f, code, wtt)
{
  var g, uf, ug;
  try {
    uf = uneval(f);
  } catch(e) { reportRoundTripIssue("Round-trip with uneval: can't uneval", code, null, null, errorToString(e)); return; }
  
  checkForCookies(uf);

  if (wtt.checkRecompiling) {
    try {
      g = eval("(" + uf + ")");
      ug = uneval(g);
      if (wtt.checkForMismatch && ug != uf) {
        reportRoundTripIssue("Round-trip with uneval: mismatch", code, uf, ug, "mismatch");
        wtt.checkForMismatch = false;
      }
    } catch(e) { reportRoundTripIssue("Round-trip with uneval: error", code, uf, ug, errorToString(e)); }
  }
}

function checkForCookies(code)
{
  // http://lxr.mozilla.org/seamonkey/source/js/src/jsopcode.c#1613
  // These are things that shouldn't appear in decompilations.
  if (code.indexOf("/*EXCEPTION") != -1
   || code.indexOf("/*RETSUB") != -1
   || code.indexOf("/*FORELEM") != -1
   || code.indexOf("/*WITH") != -1)
    printAndStop(code)
}

function reportRoundTripIssue(issue, code, fs, gs, e)
{
  if (e.indexOf("missing variable name") != -1) {
    dumpln("Bug 355667 sure is annoying!");
    return;
  }
  
  if (e.indexOf("invalid object initializer") != -1) {
    dumpln("Ignoring bug 452561.");
    return;
  }
  
  if (e.indexOf("illegal XML character") != -1) {
    dumpln("Ignoring bug 355674.");
    return;
  }
  
  if (e.indexOf("missing ; after for-loop condition") != -1) {
    dumpln("Looks like bug 460504.");
    return;
  }

  if (e == "mismatch" && fs.match(/(true|false) (\&\&|\|\|)/)) {
    dumpln("Ignoring bug 460158.");
    return;
  }
  
  var message = issue + "\n\n" +
                "Code: " + uneval(code) + "\n\n" +  
                "fs: " + fs + "\n\n" +
                "gs: " + gs + "\n\n" +
                "error: " + e;

  printAndStop(message);
}


/*************************************************
 * EXPRESSION DECOMPILATION & VALUE UNEVAL TESTS *
 *************************************************/


function testUneval(o)
{
  // If it happens to return an object, especially an array or hash, 
  // let's test uneval.  Note that this is a different code path than decompiling
  // an array literal within a function, although the two code paths often have
  // similar bugs!

  var uo, euo, ueuo;

  try {
    uo = uneval(o);
  } catch(e) {
    if (errorToString(e).indexOf("called on incompatible") != -1) {
      dumpln("Ignoring bug 379528!".toUpperCase());
      return;
    }
    else
      throw e;
  }

  if (uo == "({})") {
    // ?
    return;
  }
  
  if (testUnevalString(uo)) {
    // count=946; tryItOut("return (({ set x x (x) { yield  /x/g  } , x setter: ({}).hasOwnProperty }));");
    uo = uo.replace(/\[native code\]/g, "");
    if (uo.charAt(0) == "/")
      return; // ignore bug 362582
    
    try {
      euo = eval(uo); // if this throws, something's wrong with uneval, probably
    } catch(e) {
      dumpln("The string returned by uneval failed to eval!");
      dumpln("The string was: " + uo);
      printAndStop(e);
      return;
    }
    ueuo = uneval(euo);
    if (ueuo != uo) {
      printAndStop("Mismatch with uneval/eval on the function's return value! " + "\n" + uo + "\n" + ueuo);
    }
  } else {
    dumpln("Skipping re-eval test");
  }
}


function testUnevalString(uo)
{
  var uowlb = uo.replace(/\n/g, " ").replace(/\r/g, " ");

  return true
      &&  uo.indexOf("[native code]") == -1                // ignore bug 384756
      &&  uo.indexOf(":<") == -1  // ignore the combination of bug 334628 with bug 379519(a)
      && (uo.indexOf("#") == -1 || uo.indexOf("<") == -1 || uo.indexOf(">") == -1)  // ignore bug 379519(b)
      && (uo.indexOf("{") == -1 || uo.indexOf("<") == -1 || uo.indexOf(">") == -1)  // ignore bug 463360
      && (uo.indexOf("}") == -1 || uo.indexOf("<") == -1 || uo.indexOf(">") == -1)  // ignore bug 463360
      && (uo.indexOf("#") == -1)                           // ignore bug 328745 (ugh)
      && (uo.indexOf("{") == -1 || uo.indexOf(":") == -1)  // ignore bug 379525 hard (ugh!)
      &&  uo.indexOf("NaN") == -1                          // ignore bug 379521
      &&  uo.indexOf("Infinity") == -1                     // ignore bug 379521
      &&  uo.indexOf("[,") == -1                           // avoid  bug 379551
      &&  uo.indexOf(", ,") == -1                          // avoid  bug 379551
      &&  uo.indexOf(",]") == -1                           // avoid  bug 334628 / bug 379525?
      &&  uo.indexOf("[function") == -1                    // avoid  bug 380379?
      &&  uo.indexOf("[(function") == -1                   // avoid  bug 380379?
      && !uowlb.match(/new.*Error/)                        // ignore bug 380578
      && !uowlb.match(/<.*\/.*>.*<.*\/.*>/)                // ignore bug 334628
      && !(uo == "{}" && !jsshell)                         // ignore bug 380959
  ;
}


function checkErrorMessage(err, code)
{
  if (code.indexOf("<") != -1 && code.indexOf(">") != -1) {
    // Ignore E4X issues: bug 465908, bug 380946, etc.
    return;
  }
  
  // Checking to make sure DVG is behaving (and not, say, playing with uninitialized memory)
  if (engine == ENGINE_SPIDERMONKEY_TRUNK) {
    checkErrorMessage2(err, "TypeError: ", " is not a function");
    checkErrorMessage2(err, "TypeError: ", " is not a constructor");
    checkErrorMessage2(err, "TypeError: ", " is undefined");
  }
  
  // These should probably be tested too:XML.ignoreComments
  // XML filter is applied to non-XML value ...
  // invalid 'instanceof' operand ...
  // invalid 'in' operand ...
  // missing argument 0 when calling function ...
  // ... has invalid __iterator__ value ... (two of them!!)
}

function checkErrorMessage2(err, prefix, suffix)
{
  var P = prefix.length;
  var S = suffix.length;
  if (err.substr(0, P) == prefix) {
    if (err.substr(-S, S) == suffix) {
      var dvg = err.substr(11, err.length - P - S);
      print("Testing an expression in a recent error message: " + dvg);
      
      // These error messages can involve decompilation of expressions (DVG),
      // but in some situations they can just be uneval of a value.  In those
      // cases, we don't want to complain about known uneval bugs.
      if (!testUnevalString(dvg)) {
        print("Ignoring error message string because it looks like a known-bogus uneval");
        return;
      }

      if (dvg.match(/\#\d\=\</)) {
        print("Ignoring bug 380946");
        return;
      }
      
      if (dvg == "") {
        print("Ignoring E4X uneval bogosity"); 
        // e.g. the error message from (<x/>.(false))()
        // bug 465908, bug 380946, etc.
        return;
      }

      try {
        eval("(function() { return (" + dvg + "); })");
      } catch(e) {
        printAndStop("DVG has apparently failed us: " + e);
      }
    }
  }
}




/**************************
 * PARENTHESIZATION TESTS *
 **************************/


// Returns an array of strings of length (code.length-2), 
// each having one pair of matching parens removed.
// Assumes all parens in code are significant.  This assumption fails
// for strings or regexps, but whatever.
function deParen(code)
{
  // Get a list of locations of parens.
  var parenPairs = []; // array of { left : int, right : int } (indices into code string)
  var unmatched = []; // stack of indices into parenPairs

  var i, c;
  
  for (i = 0; i < code.length; ++i) {
    c = code.charCodeAt(i);
    if (c == 40) {
      // left paren
      unmatched.push(parenPairs.length);
      parenPairs.push({ left: i });
    } else if (c == 41) { 
      // right paren
      if (unmatched.length == 0)
        return []; // eep! unmatched rparen!
      parenPairs[unmatched.pop()].right = i;
    }
  }
  
  if (unmatched.length > 0)
    return []; // eep! unmatched lparen!
    
  var rs = [];
  
  // Don't add spaces in place of the parens, because we don't
  // want to detect things like (5).x as being unnecessary use
  // of parens.
  
  for (i = 0; i < parenPairs.length; ++i) {
    var left = parenPairs[i].left, right = parenPairs[i].right;
    rs.push(
        code.substr(0, left)
      + code.substr(left + 1, right - (left + 1))
      + code.substr(right + 1)
    );
  }
  
  return rs;
}

// print(uneval(deParen("for (i = 0; (false); ++i) { x(); }")));
// print(uneval(deParen("[]")));

function testForExtraParens(f, code)
{
  var code = code.replace(/\n/g, " ").replace(/\r/g, " "); // regexps can't match across lines

  var uf = "" + f;

  // numbers get more parens than they need
  if (uf.match(/\(\d/)) return;

  if (uf.indexOf("(<") != -1) return; // bug 381204
  if (uf.indexOf(".(") != -1) return; // bug 381207
  if (uf.indexOf("else if") != -1) return; // bug 381742
  if (code.indexOf("new") != -1) return; // "new" is weird. what can i say?
  if (code.indexOf("let") != -1) return; // reasonable to overparenthesize "let" (see expclo#c33)
  if (code.match(/for.*in.*=/)) return; // bug 381213
  if (code.match(/\:.*function/)) return; // why?
  if (uf.indexOf("(function") != -1) return; // expression closures over-parenthesize

  if (code.match(/for.*yield/)) return; // why?
  if (uf.indexOf("= (yield") != -1) return;
  if (uf.indexOf(":(yield") != -1) return;
  if (uf.indexOf(": (yield") != -1) return;
  if (uf.indexOf(", (yield") != -1) return;
  if (uf.indexOf("[(yield") != -1) return;
  if (uf.indexOf("yield") != -1) return; // i give up on yield

  // Sanity check
  var euf = eval("(" + uf + ")");
  var ueuf = "" + euf;
  if (ueuf != uf)
    printAndStop("Shouldn't the earlier round-trip test have caught this?");

  var dps = deParen(uf);
  // skip the first, which is the function's formal params.

  for (var i = 1; i < dps.length; ++i) {
    var uf2 = dps[i];
    
    try {
      var euf2 = eval("(" + uf2 + ")");
    } catch(e) { /* print("The latter did not compile.  That's fine."); */ continue; }
  
    var ueuf2 = "" + euf2
  
    if (ueuf2 == ueuf) {
      print(uf);
      print("    vs    ");
      print(uf2);
      print("Both decompile as:");
      print(ueuf);
      printAndStop("Unexpected match!!!  Extra parens!?");
    }
  }
}


/********************
 * DISASSEMBLY TEST *
 ********************/

// Finds decompiler bugs and bytecode inefficiencies by complaining when a round trip
// through the decompiler changes the bytecode.
function checkRoundTripDisassembly(f, code)
{
  if (code.match(/for.*\(.*;.*\(.*\).*;.*\)/)) {
    dumpln("checkRoundTripDisassembly: ignoring what might be a parenthesized for-loop condition (bug 475849)");
    return;
  }
  
  if (code.indexOf("[@") != -1 ||code.indexOf("[*") != -1 || code.indexOf("*::") != -1 || code.indexOf("::*") != -1) {
    dumpln("checkRoundTripDisassembly: ignoring bug 475859");
    return;
  }
  
  if (code.indexOf("=") != -1 && code.indexOf("const") != -1) {
    dumpln("checkRoundTripDisassembly: ignoring function with const and assignment, because that's boring.");
    return;
  }
  
  var uf = uneval(f);

  if (uf.match(/(true|false) (\&\&|\|\|)/)) {
    dumpln("checkRoundTripDisassembly: ignoring bug 460158.");
    return;
  }
  if (uf.indexOf("switch") != -1) {
    // Bug 355509 :(
    return;
  }
  
  if (code.indexOf("new") != code.lastIndexOf("new")) {
    dumpln("checkRoundTripDisassembly: ignoring function with two 'new' operators (bug 475848)");
    return;
  }

  if (code.indexOf("&&") != code.lastIndexOf("&&")) {
    dumpln("checkRoundTripDisassembly: ignoring && associativity issues (bug 475863)");
    return;
  }

  if (code.indexOf("||") != code.lastIndexOf("||")) {
    dumpln("checkRoundTripDisassembly: ignoring || associativity issues (bug 475863)");
    return;
  }

  if (code.match(/for.*\(.*in.*\).*if/)) {
    print("checkRoundTripDisassembly: ignoring array comprehension with 'if' (bug 475882)");
    return;
  }

  try { var g = eval(uf); } catch(e) { return; /* separate uneval test will catch this */ }

  var df = dis(f);

  if (df.indexOf("newline") != -1)
    return;
  if (df.indexOf("lineno") != -1)
    return;

  var dg = dis(g);

  if (df == dg) {
    // Happy!
    return;
  }

  if (dg.indexOf("newline") != -1) {
    // Really should just ignore these lines, instead of bailing...
    return;
  }
  if (dg.indexOf("popn") != -1 && df.indexOf("popn") == -1) {
    print("Ignoring conversion to use popn-style group assignment (bug 475843)");
    return;
  }

  var dfl = df.split("\n");
  var dgl = dg.split("\n");
  for (var i = 0; i < dfl.length && i < dgl.length; ++i) {
    if (dfl[i] != dgl[i]) {
      if (dfl[i] == "00000:  generator") {
        print("checkRoundTripDisassembly: ignoring loss of generator (bug 350743)");
        return;
      }
      if (dfl[i].indexOf("goto") != -1 && dgl[i].indexOf("stop") != -1 && uf.indexOf("switch") != -1) {
        // Actually, this might just be bug 355509.
        print("checkRoundTripDisassembly: ignoring extra 'goto' in switch (bug 475838)");
        return;
      }
      if (dfl[i].indexOf("regexp null") != -1) {
        print("checkRoundTripDisassembly: ignoring 475844 / regexp");
        return;
      }
      if (dfl[i].indexOf("namedfunobj null") != -1 || dfl[i].indexOf("anonfunobj null") != -1) {
        print("checkRoundTripDisassembly: ignoring 475844 / function");
        return;
      }
      if (dfl[i].indexOf("string") != -1 && (dfl[i+1].indexOf("toxml") != -1 || dfl[i+1].indexOf("startxml") != -1)) {
        print("checkRoundTripDisassembly: ignoring e4x-string mismatch (likely bug 355674)");
        return;
      }
      if (dfl[i].indexOf("string") != -1 && df.indexOf("startxmlexpr") != -1) {
        print("checkRoundTripDisassembly: ignoring complicated e4x-string mismatch (likely bug 355674)");
        return;
      }
      if (dfl[i].indexOf("newinit") != -1 && dgl[i].indexOf("newarray 0") != -1) {
        print("checkRoundTripDisassembly: ignoring array comprehension disappearance (bug 475847)");
        return;
      }
      if (i == 0 && dfl[i].indexOf("HEAVYWEIGHT") != -1 && dgl[i].indexOf("HEAVYWEIGHT") == -1) {
        print("checkRoundTripDisassembly: ignoring unnecessarily HEAVYWEIGHT function (bug 475854)");
        return;
      }
      if (i == 0 && dfl[i].indexOf("HEAVYWEIGHT") == -1 && dgl[i].indexOf("HEAVYWEIGHT") != -1) {
        // The other direction
        // var __proto__ hoisting, for example
        print("checkRoundTripDisassembly: ignoring unnecessarily HEAVYWEIGHT function (bug 475854 comment 1)");
        return;
      }
      
      print("First line that does not match:");
      print(dfl[i]);
      print(dgl[i]);
      break;
    }
  }
  print("Function from original code:");
  print(code);
  print(df);
  print("Function from recompiling:");
  print(uf);
  print(dg);
  printAndStop("Disassembly was not stable through decompilation");
}


/*********************
 * SPECIALIZED TESTS *
 *********************/

function simpleDVGTest(code)
{
  var fullCode = "(function() { try { \n" + code + "\n; throw 1; } catch(exx) { this.nnn.nnn } })()";
  
  try {
    eval(fullCode);
  } catch(e) {
    if (e.message != "this.nnn is undefined") {
      printAndStop("Wrong error message: " + e);
    }
  }
}


function optionalTests(f, code, wtt)
{
  if (0) {
    tryHalves(code);
  }
  
  if (0 && engine == ENGINE_SPIDERMONKEY_TRUNK) {
    if (wtt.allowExec && ('sandbox' in this)) {
      f = null;
      if (trySandboxEval(code, false)) {
        dumpln("Trying it again to see if it's a 'real leak' (???)")
        trySandboxEval(code, true);
      }
    }
    return;
  }
  
  if (0 && f && engine == ENGINE_SPIDERMONKEY_TRUNK && haveUsefulDis) {
    spiderMonkeyTrapTest(f, code, wtt);
  }

  if (0 && f && wtt.allowExec && engine == ENGINE_SPIDERMONKEY_TRUNK) {
    simpleDVGTest(code);
    tryEnsureSanity();
  }
}


function spiderMonkeyTrapTest(f, code, wtt)
{
  var offsets;

  var disassembly = dis(f); // requires fix for bug 396512, which is bitrotten
  var lines = disassembly.split("\n");
  var i;
  
  offsets = [];
  
  for (i = 0; i < lines.length; ++i) {
    if (lines[i] == "main:")
      break;
    if (i + 1 == lines.length)
      printAndStop("disassembly -- no main?");
  }
  for (++i; i < lines.length; ++i) {
    if (lines[i] == "")
      break;
    if (i + 1 == lines.length)
      printAndStop("disassembly -- ended suddenly?")

    var c = lines[i].charCodeAt(0);
    var c0 = "0".charCodeAt(0);
    var c9 = "9".charCodeAt(0);
    
    if (c0 <= c && c <= c9) // e.g. |tableswitch| and |lookupswitch| add indented lists
      offsets.push(parseInt(lines[i], 10));
  }

  if (0 // triggers lots of bugs until bug 430293 is fixed
        && offsets
        && "trap" in this
        && f
        && code.indexOf("eval") == -1 // bug 432365
        ) {

    // Save for trap      
    if (wtt.allowExec && count % 2 == 0) {
      nextTrapCode = code;
      return;
    }

    // Use trap

    if (verbose)
      dumpln("About to try the trap test.");

    var ode;
    if (wtt.allowDecompile)
      ode = "" + f;
      
    if (nextTrapCode) {
      trapCode = nextTrapCode;
      nextTrapCode = null;
      print("trapCode = " + simpleSource(trapCode));
    } else {
      trapCode = "print('Trap hit!')";
    }


    trapOffset = offsets[count % offsets.length];
    print("trapOffset: " + trapOffset);
    if (!(trapOffset > -1)) {
      print(disassembly);
      print(count);
      print(uneval(offsets));
      print(offsets.length);
      printAndStop("WTF");
    }
      
    trap(f, trapOffset, trapCode);

    if (wtt.allowDecompile) {
      nde = "" + f;
      
      if (ode != nde) {
        print(ode);
        print(nde);
        printAndStop("Trap decompilation mismatch");
      }
    }

  }
}


function trySandboxEval(code, isRetry)
{
  // (function(){})() wrapping allows "return" when it's allowed outside.
  // The line breaks are to allow single-line comments within code ("//" and "<!--").

  if (!sandbox) {
    sandbox = evalcx("");
  }

  var rv = null;
  try {
    rv = evalcx("(function(){\n" + code + "\n})();", sandbox);
  } catch(e) {
    rv = "Error from sandbox: " + errorToString(e);
  }
  
  try {
    if (typeof rv != "undefined")
      dumpln(rv);
  } catch(e) {
    dumpln("Sandbox error printing: " + errorToString(e));
  }
  rv = null;
  
  if (1 || count % 100 == 0) { // count % 100 *here* is sketchy.
    dumpln("Done with this sandbox.");
    sandbox = null;
    gc();
    var currentHeapCount = countHeap()
    dumpln("countHeap: " + currentHeapCount);
    if (currentHeapCount > maxHeapCount) {
      if (maxHeapCount != 0)
        dumpln("A new record by " + (currentHeapCount - maxHeapCount) + "!");
      if (isRetry)
        throw new Error("Found a leak!");
      maxHeapCount = currentHeapCount;
      return true;
    }
  }
  
  return false;
}  
  

function tryHalves(code)
{
  // See if there are any especially horrible bugs that appear when the parser has to start/stop in the middle of something. this is kinda evil.

  // Stray "}"s are likely in secondHalf, so use new Function rather than eval.  "}" can't escape from new Function :)
  
  var f, firstHalf, secondHalf;
  
  try {
    
    firstHalf = code.substr(0, code.length / 2);
    if (verbose)
      dumpln("First half: " + firstHalf);
    f = new Function(firstHalf); 
    "" + f;
  }
  catch(e) { 
    if (verbose)
      dumpln("First half compilation error: " + e); 
  }

  try {
    secondHalf = code.substr(code.length / 2, code.length);
    if (verbose)
      dumpln("Second half: " + secondHalf);
    f = new Function(secondHalf);
    "" + f;
  }
  catch(e) {
    if (verbose)
      dumpln("Second half compilation error: " + e);   
  }
}





/***************************
 * REPRODUCIBLE RANDOMNESS *
 ***************************/
 

// this program is a JavaScript version of Mersenne Twister, with concealment and encapsulation in class,
// an almost straight conversion from the original program, mt19937ar.c,
// translated by y. okada on July 17, 2006.
// slight change by Jesse Ruderman on June 19, 2008: added "var" keyword in a few spots; pasted into fuzz.js.
// in this program, procedure descriptions and comments of original source code were not removed.
// lines commented with //c// were originally descriptions of c procedure. and a few following lines are appropriate JavaScript descriptions.
// lines commented with /* and */ are original comments.
// lines commented with // are additional comments in this JavaScript version.
// before using this version, create at least one instance of MersenneTwister19937 class, and initialize the each state, given below in c comments, of all the instances.
/*
   A C-program for MT19937, with initialization improved 2002/1/26.
   Coded by Takuji Nishimura and Makoto Matsumoto.

   Before using, initialize the state by using init_genrand(seed)
   or init_by_array(init_key, key_length).

   Copyright (C) 1997 - 2002, Makoto Matsumoto and Takuji Nishimura,
   All rights reserved.

   Redistribution and use in source and binary forms, with or without
   modification, are permitted provided that the following conditions
   are met:

     1. Redistributions of source code must retain the above copyright
        notice, this list of conditions and the following disclaimer.

     2. Redistributions in binary form must reproduce the above copyright
        notice, this list of conditions and the following disclaimer in the
        documentation and/or other materials provided with the distribution.

     3. The names of its contributors may not be used to endorse or promote
        products derived from this software without specific prior written
        permission.

   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
   "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
   LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
   A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
   CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
   EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
   PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
   PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
   LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
   NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
   SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


   Any feedback is very welcome.
   http://www.math.sci.hiroshima-u.ac.jp/~m-mat/MT/emt.html
   email: m-mat @ math.sci.hiroshima-u.ac.jp (remove space)
*/

function MersenneTwister19937()
{
	/* Period parameters */
	//c//#define N 624
	//c//#define M 397
	//c//#define MATRIX_A 0x9908b0dfUL   /* constant vector a */
	//c//#define UPPER_MASK 0x80000000UL /* most significant w-r bits */
	//c//#define LOWER_MASK 0x7fffffffUL /* least significant r bits */
	var N = 624;
	var M = 397;
	var MATRIX_A = 0x9908b0df;   /* constant vector a */
	var UPPER_MASK = 0x80000000; /* most significant w-r bits */
	var LOWER_MASK = 0x7fffffff; /* least significant r bits */
	//c//static unsigned long mt[N]; /* the array for the state vector  */
	//c//static int mti=N+1; /* mti==N+1 means mt[N] is not initialized */
	var mt = new Array(N);   /* the array for the state vector  */
	var mti = N+1;           /* mti==N+1 means mt[N] is not initialized */

	function unsigned32 (n1) // returns a 32-bits unsiged integer from an operand to which applied a bit operator.
	{
		return n1 < 0 ? (n1 ^ UPPER_MASK) + UPPER_MASK : n1;
	}

	function subtraction32 (n1, n2) // emulates lowerflow of a c 32-bits unsiged integer variable, instead of the operator -. these both arguments must be non-negative integers expressible using unsigned 32 bits.
	{
		return n1 < n2 ? unsigned32((0x100000000 - (n2 - n1)) & 0xffffffff) : n1 - n2;
	}

	function addition32 (n1, n2) // emulates overflow of a c 32-bits unsiged integer variable, instead of the operator +. these both arguments must be non-negative integers expressible using unsigned 32 bits.
	{
		return unsigned32((n1 + n2) & 0xffffffff)
	}

	function multiplication32 (n1, n2) // emulates overflow of a c 32-bits unsiged integer variable, instead of the operator *. these both arguments must be non-negative integers expressible using unsigned 32 bits.
	{
		var sum = 0;
		for (var i = 0; i < 32; ++i){
			if ((n1 >>> i) & 0x1){
				sum = addition32(sum, unsigned32(n2 << i));
			}
		}
		return sum;
	}

	/* initializes mt[N] with a seed */
	//c//void init_genrand(unsigned long s)
	this.init_genrand = function (s)
	{
		//c//mt[0]= s & 0xffffffff;
		mt[0]= unsigned32(s & 0xffffffff);
		for (mti=1; mti<N; mti++) {
			mt[mti] = 
			//c//(1812433253 * (mt[mti-1] ^ (mt[mti-1] >> 30)) + mti);
			addition32(multiplication32(1812433253, unsigned32(mt[mti-1] ^ (mt[mti-1] >>> 30))), mti);
			/* See Knuth TAOCP Vol2. 3rd Ed. P.106 for multiplier. */
			/* In the previous versions, MSBs of the seed affect   */
			/* only MSBs of the array mt[].                        */
			/* 2002/01/09 modified by Makoto Matsumoto             */
			//c//mt[mti] &= 0xffffffff;
			mt[mti] = unsigned32(mt[mti] & 0xffffffff);
			/* for >32 bit machines */
		}
	}

	/* initialize by an array with array-length */
	/* init_key is the array for initializing keys */
	/* key_length is its length */
	/* slight change for C++, 2004/2/26 */
	//c//void init_by_array(unsigned long init_key[], int key_length)
	this.init_by_array = function (init_key, key_length)
	{
		//c//int i, j, k;
		var i, j, k;
		//c//init_genrand(19650218);
		this.init_genrand(19650218);
		i=1; j=0;
		k = (N>key_length ? N : key_length);
		for (; k; k--) {
			//c//mt[i] = (mt[i] ^ ((mt[i-1] ^ (mt[i-1] >> 30)) * 1664525))
			//c//	+ init_key[j] + j; /* non linear */
			mt[i] = addition32(addition32(unsigned32(mt[i] ^ multiplication32(unsigned32(mt[i-1] ^ (mt[i-1] >>> 30)), 1664525)), init_key[j]), j);
			mt[i] = 
			//c//mt[i] &= 0xffffffff; /* for WORDSIZE > 32 machines */
			unsigned32(mt[i] & 0xffffffff);
			i++; j++;
			if (i>=N) { mt[0] = mt[N-1]; i=1; }
			if (j>=key_length) j=0;
		}
		for (k=N-1; k; k--) {
			//c//mt[i] = (mt[i] ^ ((mt[i-1] ^ (mt[i-1] >> 30)) * 1566083941))
			//c//- i; /* non linear */
			mt[i] = subtraction32(unsigned32((dbg=mt[i]) ^ multiplication32(unsigned32(mt[i-1] ^ (mt[i-1] >>> 30)), 1566083941)), i);
			//c//mt[i] &= 0xffffffff; /* for WORDSIZE > 32 machines */
			mt[i] = unsigned32(mt[i] & 0xffffffff);
			i++;
			if (i>=N) { mt[0] = mt[N-1]; i=1; }
		}
		mt[0] = 0x80000000; /* MSB is 1; assuring non-zero initial array */
	}

	/* generates a random number on [0,0xffffffff]-interval */
	//c//unsigned long genrand_int32(void)
	this.genrand_int32 = function ()
	{
		//c//unsigned long y;
		//c//static unsigned long mag01[2]={0x0UL, MATRIX_A};
		var y;
		var mag01 = new Array(0x0, MATRIX_A);
		/* mag01[x] = x * MATRIX_A  for x=0,1 */

		if (mti >= N) { /* generate N words at one time */
			//c//int kk;
			var kk;

			if (mti == N+1)   /* if init_genrand() has not been called, */
				//c//init_genrand(5489); /* a default initial seed is used */
				this.init_genrand(5489); /* a default initial seed is used */

			for (kk=0;kk<N-M;kk++) {
				//c//y = (mt[kk]&UPPER_MASK)|(mt[kk+1]&LOWER_MASK);
				//c//mt[kk] = mt[kk+M] ^ (y >> 1) ^ mag01[y & 0x1];
				y = unsigned32((mt[kk]&UPPER_MASK)|(mt[kk+1]&LOWER_MASK));
				mt[kk] = unsigned32(mt[kk+M] ^ (y >>> 1) ^ mag01[y & 0x1]);
			}
			for (;kk<N-1;kk++) {
				//c//y = (mt[kk]&UPPER_MASK)|(mt[kk+1]&LOWER_MASK);
				//c//mt[kk] = mt[kk+(M-N)] ^ (y >> 1) ^ mag01[y & 0x1];
				y = unsigned32((mt[kk]&UPPER_MASK)|(mt[kk+1]&LOWER_MASK));
				mt[kk] = unsigned32(mt[kk+(M-N)] ^ (y >>> 1) ^ mag01[y & 0x1]);
			}
			//c//y = (mt[N-1]&UPPER_MASK)|(mt[0]&LOWER_MASK);
			//c//mt[N-1] = mt[M-1] ^ (y >> 1) ^ mag01[y & 0x1];
			y = unsigned32((mt[N-1]&UPPER_MASK)|(mt[0]&LOWER_MASK));
			mt[N-1] = unsigned32(mt[M-1] ^ (y >>> 1) ^ mag01[y & 0x1]);
			mti = 0;
		}

		y = mt[mti++];

		/* Tempering */
		//c//y ^= (y >> 11);
		//c//y ^= (y << 7) & 0x9d2c5680;
		//c//y ^= (y << 15) & 0xefc60000;
		//c//y ^= (y >> 18);
		y = unsigned32(y ^ (y >>> 11));
		y = unsigned32(y ^ ((y << 7) & 0x9d2c5680));
		y = unsigned32(y ^ ((y << 15) & 0xefc60000));
		y = unsigned32(y ^ (y >>> 18));

		return y;
	}

	/* generates a random number on [0,0x7fffffff]-interval */
	//c//long genrand_int31(void)
	this.genrand_int31 = function ()
	{
		//c//return (genrand_int32()>>1);
		return (this.genrand_int32()>>>1);
	}

	/* generates a random number on [0,1]-real-interval */
	//c//double genrand_real1(void)
	this.genrand_real1 = function ()
	{
		//c//return genrand_int32()*(1.0/4294967295.0);
		return this.genrand_int32()*(1.0/4294967295.0);
		/* divided by 2^32-1 */
	}

	/* generates a random number on [0,1)-real-interval */
	//c//double genrand_real2(void)
	this.genrand_real2 = function ()
	{
		//c//return genrand_int32()*(1.0/4294967296.0);
		return this.genrand_int32()*(1.0/4294967296.0);
		/* divided by 2^32 */
	}

	/* generates a random number on (0,1)-real-interval */
	//c//double genrand_real3(void)
	this.genrand_real3 = function ()
	{
		//c//return ((genrand_int32()) + 0.5)*(1.0/4294967296.0);
		return ((this.genrand_int32()) + 0.5)*(1.0/4294967296.0);
		/* divided by 2^32 */
	}

	/* generates a random number on [0,1) with 53-bit resolution*/
	//c//double genrand_res53(void)
	this.genrand_res53 = function ()
	{
		//c//unsigned long a=genrand_int32()>>5, b=genrand_int32()>>6;
		var a=this.genrand_int32()>>>5, b=this.genrand_int32()>>>6;
		return(a*67108864.0+b)*(1.0/9007199254740992.0);
	}
	/* These real versions are due to Isaku Wada, 2002/01/09 added */
}


var rnd;

if (1) {

  // Mersenne twister: I get to set the seed, great distribution of random numbers, but pretty slow
  // (spidermonkey trunk 2008-10-08 with JIT on, makes jsfunfuzz 20% slower overall!)

  (function() {
    var fuzzMT = new MersenneTwister19937;
    var fuzzSeed = Math.floor(Math.random() * Math.pow(2,28));
    dumpln("fuzzSeed: " + fuzzSeed);
    fuzzMT.init_genrand(fuzzSeed);
    rnd = function (n) { return Math.floor(fuzzMT.genrand_real2() * n); };
    rnd.rndReal = function() { return fuzzMT.genrand_real2(); };
    rnd.fuzzMT = fuzzMT;
  })();
} else {

  // Math.random(): ok distribution of random numbers, fast

  rnd = function (n) { return Math.floor(Math.random() * n); };
}



function rndElt(a)
{ 
  if (typeof a == "string")
    dumpln("String passed to rndElt: " + a);
    
  if (typeof a == "function")
    dumpln("Function passed to rndElt: " + a);

  if (a == null)
    dumpln("Null passed to rndElt");
  
  if (!a.length) {
    dumpln("Empty thing passed to rndElt");
    return null;
  }
  
  return a[rnd(a.length)]; 
}



/**************************
 * TOKEN-LEVEL GENERATION *
 **************************/


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

// Why did I decide to toString at every step, instead of making larger and larger arrays (or more and more deeply nested arrays?).  no particular reason...

function cat(toks)
{
  if (rnd(170) == 0)
    return totallyRandom(2);
  
  var torture = (rnd(170) == 57);
  if (torture)
    dumpln("Torture!!!");
    
  var s = maybeLineBreak();
  for (var i = 0; i < toks.length; ++i) {

    // Catch bugs in the fuzzer.  An easy mistake is
    //   return /*foo*/ + ...
    // instead of
    //   return "/*foo*/" + ...
    // Unary plus in the first one coerces the string that follows to number!
    if(typeof(toks[i]) != "string") {
      dumpln("Strange item in the array passed to cat: toks[" + i + "] == " + toks[i]);
      dumpln(cat.caller)
      dumpln(cat.caller.caller)
      printAndStop('yarr')
    }
      
    if (!(torture && rnd(12) == 0))
      s += toks[i];
    
    s += maybeLineBreak();
    
    if (torture) switch(rnd(120)) {
      case 0: 
      case 1:
      case 2:
      case 3:
      case 4:
        s += maybeSpace() + totallyRandom(2) + maybeSpace();
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
      printAndStop("Strange toks[i]: " + toks[i]);

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
  if (rnd(900) == 3) 
    return rndElt(["\r", "\n", "//h\n", "/*\n*/"]); // line break to trigger semicolon insertion and stuff
  else if (rnd(400) == 3)
    return rnd(2) ? "\u000C" : "\t"; // weird space-like characters
  else
    return "";
}

function maybeSpace()
{
  if (rnd(2) == 0)
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




/*************************
 * HIGH-LEVEL GENERATION *
 *************************/


var TOTALLY_RANDOM = 100;

function makeStatement(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  var dr = rnd(depth); // instead of depth - 1;
  
  if (depth < rnd(8)) // frequently for small depth, infrequently for large depth
    return makeLittleStatement(dr);

  return (rndElt(statementMakers))(dr)
}

var varBinder = ["var ", "let ", "const ", ""];

var statementMakers = [
  // Late-defined consts can cause problems, so let's late-define them!
  function(dr) { return cat([makeStatement(dr), " const ", makeId(dr), ";"]); },

  function(dr) { return cat([makeStatement(dr), makeStatement(dr)]); },
  function(dr) { return cat([makeStatement(dr-1), "\n", makeStatement(dr-1), "\n"]); },

  // Stripping semilcolons.  What happens if semicolons are missing?  Especially with line breaks used in place of semicolons (semicolon insertion).
  function(dr) { return cat([stripSemicolon(makeStatement(dr)), "\n", makeStatement(dr)]); },
  function(dr) { return cat([stripSemicolon(makeStatement(dr)), "\n"                   ]); },
  function(dr) { return stripSemicolon(makeStatement(dr)); }, // usually invalid, but can be ok e.g. at the end of a block with curly braces

  // Blocks and loops
  function(dr) { return cat(["{", makeStatement(dr), " }"]); },
  function(dr) { return cat(["{", makeStatement(dr-1), makeStatement(dr-1), " }"]); },

  // Sequential statements
  function(dr) { return cat([makeStatement(dr-1), makeStatement(dr-1)]); },
  function(dr) { return cat([makeStatement(dr-1), makeStatement(dr-1)]); },
  function(dr) { return cat([makeStatement(dr-1), makeStatement(dr-1)]); },
  function(dr) { return cat([makeStatement(dr-1), makeStatement(dr-1)]); },
  function(dr) { return cat([makeStatement(dr-1), makeStatement(dr-1)]); },

  // "with" blocks
  function(dr) { return cat([maybeLabel(), "with", "(", makeExpr(dr), ")", makeStatementOrBlock(dr)]); }, 
  function(dr) { return cat([maybeLabel(), "with", "(", "{", makeId(dr), ": ", makeExpr(dr), "}", ")", makeStatementOrBlock(dr)]); }, 

  // C-style "for" loops
  // Two kinds of "for" loops: one with an expression as the first part, one with a var or let binding 'statement' as the first part.
  // I'm not sure if arbitrary statements are allowed there; I think not.
  function(dr) { return "/*infloop*/" + cat([maybeLabel(), "for", "(", makeExpr(dr), "; ", makeExpr(dr), "; ", makeExpr(dr), ") ", makeStatementOrBlock(dr)]); }, 
  function(dr) { return "/*infloop*/" + cat([maybeLabel(), "for", "(", rndElt(varBinder), makeId(dr),                                       "; ", makeExpr(dr), "; ", makeExpr(dr), ") ", makeStatementOrBlock(dr)]); }, 
  function(dr) { return "/*infloop*/" + cat([maybeLabel(), "for", "(", rndElt(varBinder), makeDestructuringLValue(dr), " = ", makeExpr(dr), "; ", makeExpr(dr), "; ", makeExpr(dr), ") ", makeStatementOrBlock(dr)]); }, 
  
  // C-style "for" loops for the purpose of repetition (e.g. to test tracing)
  // These don't get T'd because we don't want to set up infinite loops.
  function(dr) { return randomRepeater() + makeStatementOrBlock(dr); },

  // Unstable loops, e.g. to test tracing "multitrees" when these loops
  // happen to create type instabilities.
  function(dr) {
    var reps = 1 + rnd(12);
    var v = randomVarName();
    var mod = rnd(5) + 2;
    var target = rnd(mod);
    var loopHead = ("/*NUUL*/for (var x = 0; x < " + reps + "; ++x)").replace(/x/g, v);
    return loopHead + " { " + 
      "if (" + v + " % " + mod + " == " + target + ") { " + makeStatement(dr) + " } " +
      "else { " + makeStatement(dr) + " } " +
      " } "
  },
  
  // Type-unstable loops
  function(dr) {
    var a = makeMixedTypeArray();
    var s = "/*TUUL*/for each (let " + makeId(dr) + " in " + a + ") { " + makeStatement(dr) + " }";
    return s;
  },


  // "for..in" loops

  // -- for (key in obj)
  function(dr) { return "/*for..in*/" + cat([maybeLabel(), "for", "(", rndElt(varBinder), makeForInLHS(dr), " in ", makeExpr(dr-2), ") ", makeStatementOrBlock(dr)]); },
  // -- for (key in generator())
  function(dr) { return "/*for..in*/" + cat([maybeLabel(), "for", "(", rndElt(varBinder), makeForInLHS(dr), " in ", "(", "(", makeFunction(dr), ")", "(", makeExpr(dr), ")", ")", ")", makeStatementOrBlock(dr)]); },
  // -- for each (value in obj)
  function(dr) { return "/*for..in*/" + "/* nogeckoex bug 349964 */" + cat([maybeLabel(), " for ", " each", "(", rndElt(varBinder), makeLValue(dr), " in ", makeExpr(dr-2), ") ", makeStatementOrBlock(dr)]); },
  
  // Modify something during a loop -- perhaps the thing being looped over
  // Since we use "let" to bind the for-variables, and only do wacky stuff once, I *think* this is unlikely to hang.
//  function(dr) { return "let forCount = 0; for (let " + makeId(dr) + " in " + makeExpr(dr) + ") { if (forCount++ == " + rnd(3) + ") { " + makeStatement(dr-1) + " } }"; },

  // Hoisty "for..in" loops.  I don't know why this construct exists, but it does, and it hoists the initial-value expression above the loop.
  // With "var" or "const", the entire thing is hoisted.
  // With "let", only the value is hoisted, and it can be elim'ed as a useless statement.
  function(dr) { return "/*for..in*/" + cat([maybeLabel(), "for", "(", rndElt(varBinder), makeId(dr), " = ", makeExpr(dr), " in ", makeExpr(dr-2), ") ", makeStatementOrBlock(dr)]); },
  function(dr) { return "/*for..in*/" + cat([maybeLabel(), "for", "(", rndElt(varBinder), "[", makeId(dr), ", ", makeId(dr), "]", " = ", makeExpr(dr), " in ", makeExpr(dr-2), ") ", makeStatementOrBlock(dr)]); },

  function(dr) { return cat([maybeLabel(), "while((", makeExpr(dr), ") && 0)" /*don't split this, it's needed to avoid marking as infloop*/, makeStatementOrBlock(dr)]); },
  function(dr) { return "/*infloop*/" + cat([maybeLabel(), "while", "(", makeExpr(dr), ")", makeStatementOrBlock(dr)]); },
  function(dr) { return cat([maybeLabel(), "do ", makeStatementOrBlock(dr), " while((", makeExpr(dr), ") && 0)" /*don't split this, it's needed to avoid marking as infloop*/, ";"]); },
  function(dr) { return "/*infloop*/" + cat([maybeLabel(), "do ", makeStatementOrBlock(dr), " while", "(", makeExpr(dr), ");"]); },

  // Switch statement
  function(dr) { return cat([maybeLabel(), "switch", "(", makeExpr(dr), ")", " { ", makeSwitchBody(dr), " }"]); },
  
  // Let blocks, with and without multiple bindings, with and without initial values
  function(dr) { return cat(["let ", "(", makeLetHead(dr), ")", " { ", makeStatement(dr), " }"]); },

  // Conditionals, perhaps with 'else if' / 'else'
  function(dr) { return cat([maybeLabel(), "if(", makeExpr(dr), ") ", makeStatementOrBlock(dr)]); },
  function(dr) { return cat([maybeLabel(), "if(", makeExpr(dr), ") ", makeStatementOrBlock(dr-1), " else ", makeStatementOrBlock(dr-1)]); },
  function(dr) { return cat([maybeLabel(), "if(", makeExpr(dr), ") ", makeStatementOrBlock(dr-1), " else ", " if ", "(", makeExpr(dr), ") ", makeStatementOrBlock(dr-1)]); },
  function(dr) { return cat([maybeLabel(), "if(", makeExpr(dr), ") ", makeStatementOrBlock(dr-1), " else ", " if ", "(", makeExpr(dr), ") ", makeStatementOrBlock(dr-1), " else ", makeStatementOrBlock(dr-1)]); },

  // A tricky pair of if/else cases.
  // In the SECOND case, braces must be preserved to keep the final "else" associated with the first "if".
  function(dr) { return cat([maybeLabel(), "if(", makeExpr(dr), ") ", "{", " if ", "(", makeExpr(dr), ") ", makeStatementOrBlock(dr-1), " else ", makeStatementOrBlock(dr-1), "}"]); },
  function(dr) { return cat([maybeLabel(), "if(", makeExpr(dr), ") ", "{", " if ", "(", makeExpr(dr), ") ", makeStatementOrBlock(dr-1), "}", " else ", makeStatementOrBlock(dr-1)]); },
  
  // Expression statements
  function(dr) { return cat([makeExpr(dr), ";"]); },
  function(dr) { return cat([makeExpr(dr), ";"]); },
  function(dr) { return cat([makeExpr(dr), ";"]); },
  function(dr) { return cat([makeExpr(dr), ";"]); },
  function(dr) { return cat([makeExpr(dr), ";"]); },
  function(dr) { return cat([makeExpr(dr), ";"]); },
  function(dr) { return cat([makeExpr(dr), ";"]); },
  function(dr) { return cat(["(", makeExpr(dr), ")", ";"]); },
  function(dr) { return cat(["(", makeExpr(dr), ")", ";"]); },
  function(dr) { return cat(["(", makeExpr(dr), ")", ";"]); },
  function(dr) { return cat(["(", makeExpr(dr), ")", ";"]); },
  function(dr) { return cat(["(", makeExpr(dr), ")", ";"]); },
  function(dr) { return cat(["(", makeExpr(dr), ")", ";"]); },
  function(dr) { return cat(["(", makeExpr(dr), ")", ";"]); },

  // Exception-related statements :)
  function(dr) { return makeExceptionyStatement(dr-1) + makeExceptionyStatement(dr-1); },
  function(dr) { return makeExceptionyStatement(dr-1) + makeExceptionyStatement(dr-1); },
  function(dr) { return makeExceptionyStatement(dr); },
  function(dr) { return makeExceptionyStatement(dr); },
  function(dr) { return makeExceptionyStatement(dr); },
  function(dr) { return makeExceptionyStatement(dr); },
  function(dr) { return makeExceptionyStatement(dr); },

  // Labels. (JavaScript does not have goto, but it does have break-to-label and continue-to-label).
  function(dr) { return cat(["L", ": ", makeStatementOrBlock(dr)]); },
  
  // Functions which are called?
  // Tends to trigger OOM bugs
  // function(dr) { return cat(["/*hhh*/function ", "x", "(", ")", "{", makeStatement(dr), "}", " ", "x", "(", makeActualArgList(dr), ")"]); }
];

function maybeLabel()
{
  if (rnd(4) == 1)
    return cat([rndElt(["L", "M"]), ":"]);
  else
    return "";
}


function randomRepeater()
{
  // tracemonkey currently requires 2 iterations to record, 3 iterations to run
  var reps = 1;
  if (jitEnabled)
    reps += rnd(5);
  var v = randomVarName();
  return ("for (var x = 0; x < " + reps + "; ++x)").replace(/x/g, v);
}

function randomVarName()
{
  var i, s = "";
  for (i = 0; i < 6; ++i)
    s += String.fromCharCode(97 + rnd(26)); // a lowercase english letter
  return s;
}



function makeSwitchBody(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  var haveSomething = false;
  var haveDefault = false;
  var output = "";

  do {

    if (!haveSomething || rnd(2)) {
      // Want a case/default (or, if this is the beginning, "need").
      
      if (!haveDefault && rnd(2)) {
        output += "default: ";
        haveDefault = true;
      }
      else {
        // cases with numbers (integers?) have special optimizations that affect order when decompiling,
        // so be sure to test those well in addition to testing complicated expressions.
        output += "case " + (rnd(2) ? rnd(10) : makeExpr(depth)) + ": ";
      }

      haveSomething = true;
    }
    
    // Might want a statement.
    if (rnd(2))
      output += makeStatement(depth)

    // Might want to break, or might want to fall through.
    if (rnd(2))
      output += "break; ";
    
    if (rnd(2))
      --depth;

  } while (depth && rnd(5));
  
  return output;
}

function makeLittleStatement(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  var dr = depth - 1;

  if (rnd(4) == 1)
    return makeStatement(dr);
  
  return (rndElt(littleStatementMakers))(dr);
}

var littleStatementMakers = 
[
  // Tiny
  function(dr) { return cat([";"]); }, // e.g. empty "if" block
  function(dr) { return cat(["{", "}"]); ; }, // e.g. empty "if" block
  function(dr) { return cat([""]); },

  // Force garbage collection
  function(dr) { return "gc()"; },
  
  // Throw stuff.
  function(dr) { return cat(["throw ", makeExpr(dr), ";"]); },

  // Break/continue [to label].
  function(dr) { return cat([rndElt(["continue", "break"]), " ", rndElt(["L", "M", "", ""]), ";"]); },

  // Named and unnamed functions (which have different behaviors in different places: both can be expressions,
  // but unnamed functions "want" to be expressions and named functions "want" to be special statements)
  function(dr) { return makeFunction(dr); },
  
  // Return, yield
  function(dr) { return cat(["return ", makeExpr(dr), ";"]); },
  function(dr) { return "return;"; }, // return without a value is allowed in generators; return with a value is not.
  function(dr) { return cat(["yield ", makeExpr(dr), ";"]); }, // note: yield can also be a left-unary operator, or something like that
  function(dr) { return "yield;"; },

  // Expression statements
  function(dr) { return cat([makeExpr(dr), ";"]); },
  function(dr) { return cat([makeExpr(dr), ";"]); },
  function(dr) { return cat([makeExpr(dr), ";"]); },
  function(dr) { return cat([makeExpr(dr), ";"]); },
  function(dr) { return cat([makeExpr(dr), ";"]); },
  function(dr) { return cat([makeExpr(dr), ";"]); },
  function(dr) { return cat([makeExpr(dr), ";"]); },
  function(dr) { return cat(["(", makeExpr(dr), ")", ";"]); },
  function(dr) { return cat(["(", makeExpr(dr), ")", ";"]); },
  function(dr) { return cat(["(", makeExpr(dr), ")", ";"]); },
  function(dr) { return cat(["(", makeExpr(dr), ")", ";"]); },
  function(dr) { return cat(["(", makeExpr(dr), ")", ";"]); },
  function(dr) { return cat(["(", makeExpr(dr), ")", ";"]); },
  function(dr) { return cat(["(", makeExpr(dr), ")", ";"]); },
  
  // Various kinds of variable declarations, with and without initial values (assignment).
  function(dr) { return cat([rndElt(varBinder), makeLetHead(dr), ";"]); }, // e.g. "const [a,b] = [3,4];"
  function(dr) { return cat([rndElt(varBinder), makeLetHead(dr), ";"]); }, // e.g. "const [a,b] = [3,4];"
  function(dr) { return cat([rndElt(varBinder), makeLetHead(dr), ";"]); }, // e.g. "const [a,b] = [3,4];"
  
  // Turn on gczeal in the middle of something
  function(dr) { return "gczeal(" + makeZealLevel() + ")" + ";"; }
];


// makeStatementOrBlock exists because often, things have different behaviors depending on where there are braces.
// for example, if braces are added or removed, the meaning of "let" can change.
function makeStatementOrBlock(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  var dr = depth - 1;
  return (rndElt(statementBlockMakers))(dr)
}

var statementBlockMakers = [
  function(dr) { return makeStatement(dr); },
  function(dr) { return makeStatement(dr); },
  function(dr) { return cat(["{", makeStatement(dr), " }"]); },
  function(dr) { return cat(["{", makeStatement(dr-1), makeStatement(dr-1), " }"]); },
]


// Extra-hard testing for try/catch/finally and related things.

function makeExceptionyStatement(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  var dr = depth - 1;
  if (dr < 1)
    return makeLittleStatement(dr);

  return (rndElt(exceptionyStatementMakers))(dr);
}

var exceptionyStatementMakers = [
  function(dr) { return makeTryBlock(dr); },

  function(dr) { return makeStatement(dr); },
  function(dr) { return makeLittleStatement(dr); },

  function(dr) { return "return;" }, // return without a value can be mixed with yield
  function(dr) { return cat(["return ", makeExpr(dr), ";"]); },
  function(dr) { return cat(["yield ", makeExpr(dr), ";"]); },
  function(dr) { return cat(["throw ", makeId(dr), ";"]); },
  function(dr) { return "throw StopIteration;"; },
  function(dr) { return "this.zzz.zzz;"; }, // throws; also tests js_DecompileValueGenerator in various locations
  function(dr) { return cat([makeId(dr), " = ", makeId(dr), ";"]); },
  function(dr) { return cat([makeLValue(dr), " = ", makeId(dr), ";"]); },

  // Iteration uses StopIteration internally.
  // Iteration is also useful to test because it asserts that there is no pending exception.
  function(dr) { return "for(let y in []);"; }, 
  function(dr) { return "for(let y in " + makeMixedTypeArray(dr) + ") " + makeExceptionyStatement(dr); }, 
  
  // Brendan says these are scary places to throw: with, let block, lambda called immediately in let expr.
  // And I think he was right.
  function(dr) { return "with({}) "   + makeExceptionyStatement(dr);         },
  function(dr) { return "with({}) { " + makeExceptionyStatement(dr) + " } "; },
  function(dr) { return "let(" + makeLetHead(dr) + ") { " + makeExceptionyStatement(dr); + "}"},
  function(dr) { return "let(" + makeLetHead(dr) + ") ((function(){" + makeExceptionyStatement(dr) + "})());" },

  // Commented out due to causing too much noise on stderr and causing a nonzero exit code :/
/*
  // Generator close hooks: called during GC in this case!!!
  function(dr) { return "(function () { try { yield " + makeExpr(dr) + " } finally { " + makeStatement(dr) + " } })().next()"; },

  function(dr) { return "(function () { try { yield " + makeExpr(dr) + " } finally { " + makeStatement(dr) + " } })()"; },
  function(dr) { return "(function () { try { yield " + makeExpr(dr) + " } finally { " + makeStatement(dr) + " } })"; },
  function(dr) { 
    return "function gen() { try { yield 1; } finally { " + makeStatement(dr) + " } } var i = gen(); i.next(); i = null;";
  }

*/
];

function makeTryBlock(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  // Catches: 1/6 chance of having none
  // Catches: maybe 2 + 1/2 
  // So approximately 4 recursions into makeExceptionyStatement on average!
  // Therefore we want to keep the chance of recursing too much down...
  
  var dr = depth - rnd(3);
  

  var s = cat(["try", " { ", makeExceptionyStatement(dr), " } "]);

  var numCatches = 0;
  
  while(rnd(3) == 0) {
    // Add a guarded catch, using an expression or a function call.
    ++numCatches;
    if (rnd(2))
      s += cat(["catch", "(", makeId(dr), " if ",                 makeExpr(dr),                    ")", " { ", makeExceptionyStatement(dr), " } "]);
    else
      s += cat(["catch", "(", makeId(dr), " if ", "(function(){", makeExceptionyStatement(dr), "})())", " { ", makeExceptionyStatement(dr), " } "]);
  }
  
  if (rnd(2)) {
    // Add an unguarded catch.
    ++numCatches;
    s +=   cat(["catch", "(", makeId(dr),                                                          ")", " { ", makeExceptionyStatement(dr), " } "]);
  }
  
  if (numCatches == 0 || rnd(2) == 1) {
    // Add a finally.
    s += cat(["finally", " { ", makeExceptionyStatement(dr), " } "]);
  }
  
  return s;
}



// Creates a string that sorta makes sense as an expression
function makeExpr(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  if (depth <= 0 || (rnd(7) == 1))
    return makeTerm(depth - 1);

  var dr = rnd(depth); // depth - 1;

  var expr = (rndElt(exprMakers))(dr);
  
  if (rnd(4) == 1)
    return "(" + expr + ")";
  else
    return expr;
}

var binaryOps = [
  // Long-standing JavaScript operators, roughly in order from http://www.codehouse.com/javascript/precedence/
  " * ", " / ", " % ", " + ", " - ", " << ", " >> ", " >>> ", " < ", " > ", " <= ", " >= ", " instanceof ", " in ", " == ", " != ", " === ", " !== ",
  " & ", " | ", " ^ ", " && ", " || ", " = ", " *= ", " /= ", " %= ", " += ", " -= ", " <<= ", " >>= ", " >>>=", " &= ", " ^= ", " |= ", " , ",

  // . is special, so test it as a group of right-unary ops, a special exprMaker for property access, and a special exprMaker for the xml filtering predicate operator
  // " . ", 
];

if (haveE4X) {
  binaryOps = binaryOps.concat([
  // Binary operators added by E4X
  " :: ", " .. ", " @ ",
  // Frequent combinations of E4X things (and "*" namespace, which isn't produced by this fuzzer otherwise)
  " .@ ", " .@*:: ", " .@x:: ",
  ]);
}
  
var leftUnaryOps = [
  "--", "++", 
  "!", "+", "-", "~",
  "void ", "typeof ", "delete ", 
  "new ", // but note that "new" can also be a very strange left-binary operator
  "yield " // see http://www.python.org/dev/peps/pep-0342/ .  Often needs to be parenthesized, so there's also a special exprMaker for it.
];

var rightUnaryOps = [
  "++", "--",
];

if (haveE4X)
  rightUnaryOps = rightUnaryOps.concat([".*", ".@foo", ".@*"]);



var specialProperties = [
  "prop", 
  "__iterator__", "__count__", 
  "__noSuchMethod__",
  "__parent__", "__proto__", "constructor", "prototype"
]


// An incomplete list of builtin methods for various data types.
var objectMethods = [
  // String
  "fromCharCode", 
  
  // Strings
  "charAt", "charCodeAt", "concat", "indexOf", "lastIndexOf", "localeCompare",
  "match", "quote", "replace", "search", "slice", "split", "substr", "substring",
  "toLocaleUpperCase", "toLocaleLowerCase", "toLowerCase", "toUpperCase",
  
  // Regular expressions
  "test", "exec", 

  // Arrays
  "splice", "shift", "sort", "pop", "push", "reverse", "unshift",
  "concat", "join", "slice",

  // Array extras in JavaScript 1.6
  "map", "forEach", "filter", "some", "every", "indexOf", "lastIndexOf",

  // Array extras in JavaScript 1.8
  "reduce", "reduceRight",

  // Functions
  "call", "apply", 

  // Date
  "now", "parse", "UTC",

  // Date instances
  "getDate", "setDay", // many more not listed

  // Number
  "toExponential", "toFixed", "toLocaleString", "toPrecision",

  // General -- defined on each type of object, but wit a different implementation
  "toSource", "toString", "valueOf", "constructor", "prototype", "__proto__",

  // General -- same implementation inherited from Object.prototype
  "__defineGetter__", "__defineSetter__", "hasOwnProperty", "isPrototypeOf", "__lookupGetter__", "__lookupSetter__", "__noSuchMethod__", "propertyIsEnumerable", "unwatch", "watch"

];
    

var exprMakers =
[
  // Left-unary operators
  function(dr) { return cat([rndElt(leftUnaryOps), makeExpr(dr)]); },
  function(dr) { return cat([rndElt(leftUnaryOps), makeExpr(dr)]); },
  function(dr) { return cat([rndElt(leftUnaryOps), makeExpr(dr)]); },
  
  // Right-unary operators
  function(dr) { return cat([makeExpr(dr), rndElt(rightUnaryOps)]); },
  function(dr) { return cat([makeExpr(dr), rndElt(rightUnaryOps)]); },
  function(dr) { return cat([makeExpr(dr), rndElt(rightUnaryOps)]); },

  // Special properties: we love to set them!
  function(dr) { return cat([makeExpr(dr), ".", rndElt(specialProperties)]); },
  function(dr) { return cat([makeExpr(dr), ".", rndElt(specialProperties), " = ", makeExpr(dr)]); },
  function(dr) { return cat([makeId(dr),   ".", rndElt(specialProperties), " = ", makeExpr(dr)]); },
  
  // Methods
  function(dr) { return cat([makeExpr(dr), ".", rndElt(objectMethods), "(", makeActualArgList(dr), ")"]); },
  function(dr) { return cat([makeExpr(dr), ".", "valueOf", "(", uneval("number"), ")"]); },

  // Binary operators
  function(dr) { return cat([makeExpr(dr), rndElt(binaryOps), makeExpr(dr)]); },
  function(dr) { return cat([makeExpr(dr), rndElt(binaryOps), makeExpr(dr)]); },
  function(dr) { return cat([makeExpr(dr), rndElt(binaryOps), makeExpr(dr)]); },
  function(dr) { return cat([makeExpr(dr), rndElt(binaryOps), makeExpr(dr)]); },
  function(dr) { return cat([makeExpr(dr), rndElt(binaryOps), makeExpr(dr)]); },
  function(dr) { return cat([makeExpr(dr), rndElt(binaryOps), makeExpr(dr)]); },
  function(dr) { return cat([makeExpr(dr), rndElt(binaryOps), makeExpr(dr)]); },
  function(dr) { return cat([makeExpr(dr), rndElt(binaryOps), makeExpr(dr)]); },
  function(dr) { return cat([makeExpr(dr), rndElt(binaryOps), makeExpr(dr)]); },
  function(dr) { return cat([makeExpr(dr), rndElt(binaryOps), makeExpr(dr)]); },
  function(dr) { return cat([makeExpr(dr), rndElt(binaryOps), makeExpr(dr)]); },
  function(dr) { return cat([makeExpr(dr), rndElt(binaryOps), makeExpr(dr)]); },
  function(dr) { return cat([makeExpr(dr), rndElt(binaryOps), makeExpr(dr)]); },
  
  // Ternary operator
  function(dr) { return cat([makeExpr(dr), " ? ", makeExpr(dr), " : ", makeExpr(dr)]); },
  function(dr) { return cat([makeExpr(dr), " ? ", makeExpr(dr), " : ", makeExpr(dr)]); },

  // In most contexts, yield expressions must be parenthesized, so including explicitly parenthesized yields makes actually-compiling yields appear more often.
  function(dr) { return cat(["yield ", makeExpr(dr)]); },
  function(dr) { return cat(["(", "yield ", makeExpr(dr), ")"]); },
  
  // Array functions (including extras).  The most interesting are map and filter, I think.
  // These are mostly interesting to fuzzers in the sense of "what happens if i do strange things from a filter function?"  e.g. modify the array.. :)
  // This fuzzer isn't the best for attacking this kind of thing, since it's unlikely that the code in the function will attempt to modify the array or make it go away.
  // The second parameter to "map" is used as the "this" for the function.
  function(dr) { return cat(["[11,12,13,14]",        ".", rndElt(["map", "filter", "some", "sort"]) ]); },
  function(dr) { return cat(["[15,16,17,18]",        ".", rndElt(["map", "filter", "some", "sort"]), "(", makeFunction(dr), ", ", makeExpr(dr), ")"]); },
  function(dr) { return cat(["[", makeExpr(dr), "]", ".", rndElt(["map", "filter", "some", "sort"]), "(", makeFunction(dr), ")"]); },
  
  // RegExp replace.  This is interesting for the same reason as array extras.  Also, in SpiderMonkey, the "this" argument is weird (obj.__parent__?)
  function(dr) { return cat(["'fafafa'", ".", "replace", "(", "/", "a", "/", "g", ", ", makeFunction(dr), ")"]); },

  // Dot (property access)
  function(dr) { return cat([makeId(dr),    ".", makeId(dr)]); },
  function(dr) { return cat([makeExpr(dr),  ".", makeId(dr)]); },

  // Index into array
  function(dr) { return cat([     makeExpr(dr),      "[", makeExpr(dr), "]"]); },
  function(dr) { return cat(["(", makeExpr(dr), ")", "[", makeExpr(dr), "]"]); },

  // Containment in an array or object (or, if this happens to end up on the LHS of an assignment, destructuring)
  function(dr) { return cat([maybeSharpDecl(), "[", makeExpr(dr), "]"]); },
  function(dr) { return cat([maybeSharpDecl(), "(", "{", makeId(dr), ": ", makeExpr(dr), "}", ")"]); },

  // Sharps on random stuff?
  function(dr) { return cat([maybeSharpDecl(), makeExpr(dr)]); },

  // Functions: called immediately/not
  function(dr) { return makeFunction(dr); },
  function(dr) { return cat(["(", makeFunction(dr), ")", "(", makeActualArgList(dr), ")"]); },

  // Try to call things that may or may not be functions.
  function(dr) { return cat([     makeExpr(dr),          "(", makeActualArgList(dr), ")"]); },
  function(dr) { return cat(["(", makeExpr(dr),     ")", "(", makeActualArgList(dr), ")"]); },
  function(dr) { return cat([     makeFunction(dr),      "(", makeActualArgList(dr), ")"]); },

  // Try to test function.call heavily.
  function(dr) { return cat(["(", makeFunction(dr), ")", ".", "call", "(", makeExpr(dr), ", ", makeActualArgList(dr), ")"]); },
  
  // Binary "new", with and without clarifying parentheses, with expressions or functions
  function(dr) { return cat(["new ",      makeExpr(dr),          "(", makeActualArgList(dr), ")"]); },
  function(dr) { return cat(["new ", "(", makeExpr(dr), ")",     "(", makeActualArgList(dr), ")"]); },

  function(dr) { return cat(["new ",      makeFunction(dr),      "(", makeActualArgList(dr), ")"]); },
  function(dr) { return cat(["new ", "(", makeFunction(dr), ")", "(", makeActualArgList(dr), ")"]); },

  // Sometimes we do crazy stuff, like putting a statement where an expression should go.  This frequently causes a syntax error.
  function(dr) { return stripSemicolon(makeLittleStatement(dr)); },
  function(dr) { return ""; },

  // Let expressions -- note the lack of curly braces.
  function(dr) { return cat(["let ", "(", makeLetHead(dr), ") ", makeExpr(dr)]); },

  // Array comprehensions (JavaScript 1.7)
  function(dr) { return cat(["[", makeExpr(dr), makeComprehension(dr), "]"]); },

  // Generator expressions (JavaScript 1.8)
  function(dr) { return cat([     makeExpr(dr), makeComprehension(dr)     ]); },
  function(dr) { return cat(["(", makeExpr(dr), makeComprehension(dr), ")"]); },
  
  // Comments and whitespace
  function(dr) { return cat([" /* Comment */", makeExpr(dr)]); },
  function(dr) { return cat(["\n", makeExpr(dr)]); }, // perhaps trigger semicolon insertion and stuff
  function(dr) { return cat([makeExpr(dr), "\n"]); },

  // LValue as an expression
  function(dr) { return cat([makeLValue(dr)]); },

  // Assignment (can be destructuring)
  function(dr) { return cat([     makeLValue(dr),      " = ", makeExpr(dr)     ]); },
  function(dr) { return cat([     makeLValue(dr),      " = ", makeExpr(dr)     ]); },
  function(dr) { return cat(["(", makeLValue(dr),      " = ", makeExpr(dr), ")"]); },
  function(dr) { return cat(["(", makeLValue(dr), ")", " = ", makeExpr(dr)     ]); },

  // Destructuring assignment
  function(dr) { return cat([     makeDestructuringLValue(dr),      " = ", makeExpr(dr)     ]); },
  function(dr) { return cat([     makeDestructuringLValue(dr),      " = ", makeExpr(dr)     ]); },
  function(dr) { return cat(["(", makeDestructuringLValue(dr),      " = ", makeExpr(dr), ")"]); },
  function(dr) { return cat(["(", makeDestructuringLValue(dr), ")", " = ", makeExpr(dr)     ]); },
  
  // Destructuring assignment with lots of group assignment
  function(dr) { return cat([makeDestructuringLValue(dr), " = ", makeDestructuringLValue(dr)]); },
  
  // Modifying assignment, with operators that do various coercions
  function(dr) { return cat([makeLValue(dr), rndElt(["|=", "%=", "+=", "-="]), makeExpr(dr)]); },

  // Watchpoints (similar to setters)
  function(dr) { return cat([makeExpr(dr), ".", "watch", "(", uneval(makeId(dr)), ", ", makeFunction(dr), ")"]); },
  function(dr) { return cat([makeExpr(dr), ".", "unwatch", "(", uneval(makeId(dr)), ")"]); },
  
  // New-style getter/setter, imperative
  function(dr) { return cat([makeExpr(dr), ".", "__defineGetter__", "(", uneval(makeId(dr)), ", ", makeFunction(dr), ")"]); },
  function(dr) { return cat([makeExpr(dr), ".", "__defineSetter__", "(", uneval(makeId(dr)), ", ", makeFunction(dr), ")"]); },
  function(dr) { return cat(["this", ".", "__defineGetter__", "(", uneval(makeId(dr)), ", ", makeFunction(dr), ")"]); },
  function(dr) { return cat(["this", ".", "__defineSetter__", "(", uneval(makeId(dr)), ", ", makeFunction(dr), ")"]); },
  
  // Old-style getter/setter, imperative
  function(dr) { return cat([makeId(dr), ".", makeId(dr), " ", rndElt(["getter", "setter"]), "= ", makeFunction(dr)]); },

  // Object literal
  function(dr) { return cat(["(", "{", makeObjLiteralPart(dr), " }", ")"]); },
  function(dr) { return cat(["(", "{", makeObjLiteralPart(dr), ", ", makeObjLiteralPart(dr), " }", ")"]); },
  
  // Test js_ReportIsNotFunction heavily.
  function(dr) { return "(p={}, (p.z = " + makeExpr(dr) + ")())"; },

  // Test js_ReportIsNotFunction heavily.
  // Test decompilation for ".keyword" a bit.
  // Test throwing-into-generator sometimes.
  function(dr) { return cat([makeExpr(dr), ".", "throw", "(", makeExpr(dr), ")"]); },
  function(dr) { return cat([makeExpr(dr), ".", "yoyo",   "(", makeExpr(dr), ")"]); },

  // Throws, but more importantly, tests js_DecompileValueGenerator in various contexts.
  function(dr) { return "this.zzz.zzz"; }, 
  
  // Test eval in various contexts. (but avoid clobbering eval)
  // Test the special "obj.eval" and "eval(..., obj)" forms.
  function(dr) { return makeExpr(dr) + ".eval(" + makeExpr(dr) + ")"; },
  function(dr) { return "eval(" + uneval(makeExpr(dr)) + ", " + makeExpr(dr) + ")"; },  
  function(dr) { return "eval(" + uneval(makeStatement(dr)) + ", " + makeExpr(dr) + ")"; },
  
  // Uneval needs more testing than it will get accidentally.  No cat() because I don't want uneval clobbered (assigned to) accidentally.
  function(dr) { return "(uneval(" + makeExpr(dr) + "))"; },
  
  // Constructors.  No cat() because I don't want to screw with the constructors themselves, just call them.
  function(dr) { return "new " + rndElt(constructors) + "(" + makeActualArgList(dr) + ")"; },
  function(dr) { return          rndElt(constructors) + "(" + makeActualArgList(dr) + ")"; },

  // Turn on gczeal in the middle of something
  function(dr) { return "gczeal(" + makeZealLevel() + ")"; }
];

function makeZealLevel()
{
  // gczeal is really slow, so only turn it on very occasionally.
  switch(rnd(100)) {
  case 0:
    return "2";
  case 1:
    return "1";
  default:
    return "0";
  }
}

if (haveE4X) {
  exprMakers = exprMakers.concat([
    // XML filtering predicate operator!  It isn't lexed specially; there can be a space between the dot and the lparen.
    function(dr) { return cat([makeId(dr),  ".", "(", makeExpr(dr), ")"]); },
    function(dr) { return cat([makeE4X(dr),  ".", "(", makeExpr(dr), ")"]); },
  ]);
}


var constructors = [
  "Error", "RangeError", "Exception",
  "Function", "Date", "RegExp", "String", "Array", "Object", "Number", "Boolean", 
  "Iterator"
];

function maybeSharpDecl()
{
  if (rnd(3) == 0)
    return cat(["#", "" + (rnd(3)), "="]);
  else
    return "";
}


function makeObjLiteralPart(dr)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(dr);

  switch(rnd(8))
  {
    // Old-style literal getter/setter
    case 0: return cat([makeId(dr), " getter: ", makeFunction(dr)]);
    case 1: return cat([makeId(dr), " setter: ", makeFunction(dr)]);
    
    // New-style literal getter/setter
    case 2: return cat([" get ", makeId(dr), maybeName(dr), "(", makeFormalArgList(dr-1), ")", makeFunctionBody(dr)]);
    case 3: return cat([" set ", makeId(dr), maybeName(dr), "(", makeFormalArgList(dr-1), ")", makeFunctionBody(dr)]);
    


/*
    case 3: return cat(["toString: ", makeFunction(dr), "}", ")"]);
    case 4: return cat(["toString: function() { return this; } }", ")"]); }, // bwahaha
    case 5: return cat(["toString: function() { return " + makeExpr(dr) + "; } }", ")"]); },
    case 6: return cat(["valueOf: ", makeFunction(dr), "}", ")"]); },
    case 7: return cat(["valueOf: function() { return " + makeExpr(dr) + "; } }", ")"]); },
*/

    default: return cat([makeId(dr), ": ", makeExpr(dr)]);
  }
}




function makeFunction(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  var dr = depth - 1;
  
  if(rnd(5) == 1)
    return makeExpr(dr);

  return (rndElt(functionMakers))(dr);
}


function makeFunPrefix(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  switch(rnd(20)) {
// Leaving this stuff out until bug 381203 is fixed.
// Eventually this stuff should be moved from functionMakers to somewhere
// like statementMakers, right?
//    case 0: return "getter ";
//    case 1: return "setter ";
    default: return "";
  }
}

function maybeName(depth)
{
  if (rnd(2) == 0)
    return " " + makeId(depth) + " ";
  else
    return "";
}

function makeFunctionBody(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  switch(rnd(4)) {
    case 0: return cat([" { ", makeStatement(depth - 1),   " } "]);
    case 1: return cat([" { ", "return ", makeExpr(depth), " } "]);
    case 2: return cat([" { ", "yield ",  makeExpr(depth), " } "]);
    case 3: return makeExpr(depth); // make an "expression closure"
  }
}




var functionMakers = [
  // Note that a function with a name is sometimes considered a statement rather than an expression.

  // Functions and expression closures
  function(dr) { return cat([makeFunPrefix(dr), "function", " ", maybeName(dr), "(", makeFormalArgList(dr), ")", makeFunctionBody(dr)]); },
  function(dr) { return cat([makeFunPrefix(dr), "function", " ", maybeName(dr), "(", makeFormalArgList(dr), ")", makeFunctionBody(dr)]); },
  function(dr) { return cat([makeFunPrefix(dr), "function", " ", maybeName(dr), "(", makeFormalArgList(dr), ")", makeFunctionBody(dr)]); },
  function(dr) { return cat([makeFunPrefix(dr), "function", " ", maybeName(dr), "(", makeFormalArgList(dr), ")", makeFunctionBody(dr)]); },
  
  // Methods
  function(dr) { return cat([makeExpr(dr), ".", rndElt(objectMethods)]); }, 
  function(dr) { return cat([makeExpr(dr), ".", rndElt(objectMethods)]); }, 
  function(dr) { return cat([makeExpr(dr), ".", rndElt(objectMethods)]); }, 
  function(dr) { return cat([makeExpr(dr), ".", rndElt(objectMethods)]); }, 

  // The identity function
  function(dr) { return "function(q) { return q; }" },

  // A generator that does something
  function(dr) { return "function(y) { yield y; " + makeStatement(dr) + "; yield y; }" }, 
  
  // A generator expression -- kinda a function??
  function(dr) { return "(1 for (x in []))"; },
  
  // Special functions that might have interesting results, especially when called "directly" by things like string.replace or array.map.
  function(dr) { return "eval" }, // eval is interesting both for its "no indirect calls" feature and for the way it's implemented -- a special bytecode.
  function(dr) { return "new Function" }, // this won't be interpreted the same way for each caller of makeFunction, but that's ok
  function(dr) { return "(new Function(" + uneval(makeStatement(dr)) + "))"; },
  function(dr) { return "Function" }, // without "new"!  it does seem to work...
  function(dr) { return "gc" },
  function(dr) { return "Math.sin" },
  function(dr) { return "Math.pow" },
  function(dr) { return "/a/gi" }, // in Firefox, at least, regular expressions can be used as functions: e.g. "hahaa".replace(/a+/g, /aa/g) is "hnullhaa"!
];
  


function makeLetHead(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  if (rnd(2) == 1)
    return makeLetHeadItem(depth);
  else
    return makeLetHeadItem(depth) + ", " + makeLetHeadItem(depth - 1);
}

function makeLetHeadItem(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  var dr = depth - 1;
  
  // 0 or more things being declared
  var lhs = (rnd(3) == 1) ? makeDestructuringLValue(dr) : makeId(dr);
  
  // initial value
  var rhs = (rnd(2) == 1) ? (" = " + makeExpr(dr)) : "";
  
  return lhs + rhs;
}


function makeActualArgList(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  var nArgs = rnd(3);

  if (nArgs == 0)
    return "";

  var argList = makeExpr(depth);

  for (var i = 1; i < nArgs; ++i)
    argList += ", " + makeExpr(depth - i);

  return argList;
}

function makeFormalArgList(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  var nArgs = rnd(3);

  if (nArgs == 0)
    return "";

  var argList = makeFormalArg(depth)

  for (var i = 1; i < nArgs; ++i)
    argList += ", " + makeFormalArg(depth - i);
    
  return argList;
}

function makeFormalArg(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  if (rnd(4) == 1)
    return makeDestructuringLValue(depth);
  
  return makeId(depth);
}


function makeId(depth) 
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);
  
  var dr = depth; // !

  switch(rnd(200))
  {
  case 0:
    return makeTerm(dr);
  case 1:  
    return makeExpr(dr);
  case 2: case 3: case 4: case 5:  
    return makeLValue(dr);
  case 6: case 7:
    return makeDestructuringLValue(dr);
  case 8: case 9: case 10:
    // some keywords that can be used as identifiers in some contexts (e.g. variables, function names, argument names)
    // but that's annoying, and some of these cause lots of syntax errors.
    return rndElt(["get", "set", "getter", "setter", "delete", "let", "yield", "each"]);
  case 11: case 12: case 13:
    return "function::" + makeId(dr);
  case 14:
    return "x::" + makeId(dr);
  case 15: case 16:
    return rndElt(specialProperties);
  }

  return rndElt(["x", "x", "x", "x", "x", "x", "x", "x", // repeat "x" so it's likely to be bound more than once, causing "already bound" errors, elimination of assign-to-const, or conflicts
                 "x1", "x2", "x3", "x4", "x5",
                 "c", // this appears as a variable name in tryItOut, so eval has fun with it
                 "y", "window", "this", "\u3056", "NaN",
//                 "valueOf", "toString", // e.g. valueOf getter :P // bug 381242, etc
                 "functional", // perhaps decompiler code looks for "function"?
                 " " // [k, v] becomes [, v] -- test how holes are handled in unexpected destructuring
                  ]);

  // window is a const (in the browser), so some attempts to redeclare it will cause errors

  // eval is interesting because it cannot be called indirectly. and maybe also because it has its own opcode in jsopcode.tbl.
  // but bad things happen if you have "eval setter"... so let's not put eval in this list.
}


function makeComprehension(dr)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(dr);

  if (dr < 0)
    return "";

  switch(rnd(5)) {
  case 0:
    return "";
  case 1:
    return cat([" for ",          "(", makeForInLHS(dr), " in ", makeExpr(dr-2),           ")"]) + makeComprehension(dr - 1);
  case 2:
    return cat([" for ", "each ", "(", makeId(dr),       " in ", makeExpr(dr-2),           ")"]) + makeComprehension(dr - 1);
  case 3:
    return cat([" for ", "each ", "(", makeId(dr),       " in ", makeMixedTypeArray(dr-2), ")"]) + makeComprehension(dr - 1);
  case 4:    
    return cat([" if ", "(", makeExpr(dr-2), ")"]); // this is always last (and must be preceded by a "for", oh well)
  }
}




// for..in LHS can be a single variable OR it can be a destructuring array of exactly two elements.
function makeForInLHS(dr)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(dr);

// JS 1.7 only (removed in JS 1.8)
//
//  if (version() == 170 && rnd(4) == 0)
//    return cat(["[", makeLValue(dr), ", ", makeLValue(dr), "]"]);

  return makeLValue(dr);
}


function makeLValue(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  if (depth <= 0 || (rnd(2) == 1))
    return makeId(depth - 1);

  var dr = rnd(depth);

  return (rndElt(lvalueMakers))(dr);
}


var lvalueMakers = [
  // Simple variable names :)
  function(dr) { return cat([makeId(dr)]); },

  // Destructuring
  function(dr) { return makeDestructuringLValue(dr); },
  function(dr) { return "(" + makeDestructuringLValue(dr) + ")"; },
  
  // Properties
  function(dr) { return cat([makeId(dr), ".", makeId(dr)]); },
  function(dr) { return cat([makeExpr(dr), ".", makeId(dr)]); },
  function(dr) { return cat([makeExpr(dr), "[", "'", makeId(dr), "'", "]"]); },

  // Special properties
  function(dr) { return cat([makeId(dr), ".", rndElt(specialProperties)]); },

  // Certain functions can act as lvalues!  See JS_HAS_LVALUE_RETURN in js engine source.
  function(dr) { return cat([makeId(dr), "(", makeExpr(dr), ")"]); },
  function(dr) { return cat(["(", makeExpr(dr), ")", "(", makeExpr(dr), ")"]); },

  // Parenthesized lvalues can cause problems ;)
  function(dr) { return cat(["(", makeLValue(dr), ")"]); },

  function(dr) { return makeExpr(dr); } // intentionally bogus, but not quite garbage.
];

function makeDestructuringLValue(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  var dr = depth - 1;

  if (dr < 0 || rnd(4) == 1)
    return makeId(dr);

  if (rnd(6) == 1)
    return makeLValue(dr);

  return (rndElt(destructuringLValueMakers))(dr);
}

var destructuringLValueMakers = [
  // destructuring assignment: arrays
  function(dr) 
  { 
    var len = rnd(dr);
    if (len == 0)
      return "[]";
      
    var Ti = [];
    Ti.push("[");
    Ti.push(maybeMakeDestructuringLValue(dr));
    for (var i = 1; i < len; ++i) {
      Ti.push(", ");
      Ti.push(maybeMakeDestructuringLValue(dr));    
    }
    
    Ti.push("]");
    
    return cat(Ti);    
  },

  // destructuring assignment: objects
  function(dr)
  {
    var len = rnd(dr);
    if (len == 0)
      return "{}";
    var Ti = [];
    Ti.push("{");
    for (var i = 0; i < len; ++i) {
      if (i > 0)
        Ti.push(", ");
      Ti.push(makeId(dr));
      if (rnd(3)) {
        Ti.push(": ");
        Ti.push(makeDestructuringLValue(dr));
      } // else, this is a shorthand destructuring, treated as "id: id".
    }
    Ti.push("}");
    
    return cat(Ti);
  }
];

// Allow "holes".
function maybeMakeDestructuringLValue(depth)
{
  if (rnd(2) == 0)
    return ""
    
  return makeDestructuringLValue(depth)
}



function makeTerm(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  return (rndElt(termMakers))(depth);
}

var termMakers = [
  // Variable names
  function(dr) { return makeId(dr); },

  // Simple literals (no recursion required to make them)
  function(dr) { return rndElt([ 
    // Arrays
    "[]", "[1]", "[[]]", "[[1]]", "[,]", "[,,]", "[1,,]",
    // Objects
    "{}", "({})", "({a1:1})", 
    // Possibly-destructuring arrays
    "[z1]", "[z1,,]", "[,,z1]",
    // Possibly-destructuring objects
    "({a2:z2})",
    // Sharp use
    "#1#",
    // Sharp creation and use
    "#1=[#1#]", "#3={a:#3#}",
    "function(id) { return id }",
    "function ([y]) { }",
    "(function ([y]) { })()",
    
    "arguments"
    ]);
  },
  function(dr) { return rndElt([ "0.1", ".2", "3", "1.3", "4.", "5.0000000000000000000000", "1.2e3", "1e81", "1e+81", "1e-81", "1e4", "0", "-0", "(-0)", "-1", "(-1)", "0x99", "033", (""+Math.PI), "3/0", "-3/0", "0/0"
    // these are commented out due to bug 379294
    // "0x2D413CCC", "0x5a827999", "0xB504F332", "(0x50505050 >> 1)"
  ]); },
  function(dr) { return rndElt([ "true", "false", "undefined", "null"]); },
  function(dr) { return rndElt([ "this", "window" ]); },
  function(dr) { return rndElt([" \"\" ", " '' ", " /x/ ", " /x/g "]) },
];

if (haveE4X) {
  // E4X literals
  termMakers = termMakers.concat([
  function(dr) { return rndElt([ "<x/>", "<y><z/></y>"]); },
  function(dr) { return rndElt([ "@foo" /* makes sense in filtering predicates, at least... */, "*", "*::*"]); },
  function(dr) { return makeE4X(dr) }, // xml
  function(dr) { return cat(["<", ">", makeE4X(dr), "<", "/", ">"]); }, // xml list
  ]);
}


function maybeMakeTerm(depth)
{
  if (rnd(2))
    return makeTerm(depth - 1);
  else
    return "";
}


function makeCrazyToken()
{
  if (rnd(2) == 0) {
    // This can be more aggressive once bug 368694 is fixed.
    return String.fromCharCode(32 + rnd(128 - 32));
  }

  return rndElt([

  // Some of this is from reading jsscan.h.

  // Comments; comments hiding line breaks.
  "//", UNTERMINATED_COMMENT, (UNTERMINATED_COMMENT + "\n"), "/*\n*/", 
  
  // groupers (which will usually be unmatched if they come from here ;)
  "[", "]", 
  "{", "}", 
  "(", ")",
  
  // a few operators
  "!", "@", "%", "^", "*", "|", ":", "?", "'", "\"", ",", ".", "/", 
  "~", "_", "+", "=", "-", "++", "--", "+=", "%=", "|=", "-=", 
  "#", "#1", "#1=", // usually an "invalid character", but used as sharps too
  
  // most real keywords plus a few reserved keywords
  " in ", " instanceof ", " let ", " new ", " get ", " for ", " if ", " else ", " else if ", " try ", " catch ", " finally ", " export ", " import ", " void ", " with ", 
  " default ", " goto ", " case ", " switch ", " do ", " /*infloop*/while ", " return ", " yield ", " break ", " continue ", " typeof ", " var ", " const ", 
    
  // several keywords can be used as identifiers. these are just a few of them.
  " enum ", // JS_HAS_RESERVED_ECMA_KEYWORDS
  " debugger ", // JS_HAS_DEBUGGER_KEYWORD
  " super ", // TOK_PRIMARY!

  " this ", // TOK_PRIMARY!
  " null ", // TOK_PRIMARY!
  " undefined ", // not a keyword, but a default part of the global object
  "\n", // trigger semicolon insertion, also acts as whitespace where it might not be expected
  "\r", 
  "\u2028", // LINE_SEPARATOR?
  "\u2029", // PARA_SEPARATOR?
  "<" + "!" + "--", // beginning of HTML-style to-end-of-line comment (!)
  "--" + ">", // end of HTML-style comment
  "",
  "\0", // confuse anything that tries to guess where a string ends. but note: "illegal character"!
  ]);
}


function makeE4X(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

  if (depth <= 0)
    return cat(["<", "x", ">", "<", "y", "/", ">", "<", "/", "x", ">"]);
    
  var dr = depth - 1;
  
  var y = [
    function(dr) { return '<employee id="1"><name>Joe</name><age>20</age></employee>' },
    function(dr) { return cat(["<", ">", makeSubE4X(dr), "<", "/", ">"]); }, // xml list

    function(dr) { return cat(["<", ">", makeExpr(dr), "<", "/", ">"]); }, // bogus or text
    function(dr) { return cat(["<", "zzz", ">", makeExpr(dr), "<", "/", "zzz", ">"]); }, // bogus or text
    
    // mimic parts of this example at a time, from the e4x spec: <x><{tagname} {attributename}={attributevalue+attributevalue}>{content}</{tagname}></x>;

    function(dr) { var tagId = makeId(dr); return cat(["<", "{", tagId, "}", ">", makeSubE4X(dr), "<", "/", "{", tagId, "}", ">"]); },
    function(dr) { var attrId = makeId(dr); var attrValExpr = makeExpr(dr); return cat(["<", "xxx", " ", "{", attrId, "}", "=", "{", attrValExpr, "}", " ", "/", ">"]); },
    function(dr) { var contentId = makeId(dr); return cat(["<", "xxx", ">", "{", contentId, "}", "<", "/", "xxx", ">"]); },
    
    // namespace stuff
    function(dr) { var contentId = makeId(dr); return cat(['<', 'bbb', ' ', 'xmlns', '=', '"', makeExpr(dr), '"', '>', makeSubE4X(dr), '<', '/', 'bbb', '>']); },
    function(dr) { var contentId = makeId(dr); return cat(['<', 'bbb', ' ', 'xmlns', ':', 'ccc', '=', '"', makeExpr(dr), '"', '>', '<', 'ccc', ':', 'eee', '>', '<', '/', 'ccc', ':', 'eee', '>', '<', '/', 'bbb', '>']); },
    
    function(dr) { return makeExpr(dr); },
    
    function(dr) { return makeSubE4X(dr); }, // naked cdata things, etc.
  ]
  
  return (rndElt(y))(dr);
}

function makeSubE4X(depth)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(depth);

// Bug 380431
//  if (rnd(8) == 0)
//    return "<" + "!" + "[" + "CDATA[" + makeExpr(depth - 1) + "]" + "]" + ">"

  if (depth < -2)
    return "";

  var y = [
    function(depth) { return cat(["<", "ccc", ":", "ddd", ">", makeSubE4X(depth - 1), "<", "/", "ccc", ":", "ddd", ">"]); },
    function(depth) { return makeE4X(depth) + makeSubE4X(depth - 1); },
    function(depth) { return "yyy"; },
    function(depth) { return cat(["<", "!", "--", "yy", "--", ">"]); }, // XML comment
// Bug 380431
//    function(depth) { return cat(["<", "!", "[", "CDATA", "[", "zz", "]", "]", ">"]); }, // XML cdata section
    function(depth) { return " "; },
    function(depth) { return ""; },
  ];
  
  return (rndElt(y))(depth);
}

function makeMixedTypeArray()
{
  
  var a = [
           "1", "2", "0", "-0",
           "1.5", "-1e81",
           "(1/0)", "(-1/0)", "(0/0)",
           "(void 0)", "null", 
           "''", "new String('')",
           "'q'", "new String('q')",
           "false", "true", "new Boolean(true)", "new Boolean(false)",
           "/x/", "function(){}", "{}", "[]", "this", "eval", "arguments",
           "x"
         ];
  // Pick two or three of those
  var b = [rndElt(a), rndElt(a), rndElt(a)];
  var c = [];
  // var count = rnd(15);
  var count = 10;
  for (var j = 0; j < count; ++j)
    c.push(rndElt(b));
  return "[" + c.join(", ") + "]";
}





var count = 0;
var verbose = false;


var maxHeapCount = 0;
var sandbox = null;
var nextTrapCode = null;
// https://bugzilla.mozilla.org/show_bug.cgi?id=394853#c19
//try { eval("/") } catch(e) { }
// Remember the number of countHeap.
tryItOut("");
init();



/*
// Aggressive test for type-unstable arrays
count = 1;
for (var j = 0; j < 20000; ++j) {
  x = null;
  if (j % 100 == 0) gc();
  var a = makeMixedTypeArray();
  print(uneval(a));
  var s = "for each (let i in " + a + ") { }";
  //var s = "[i for each (i in " + a + ") if (i)]";
  eval(s);
}
throw 1;
*/


/**************************************
 * To reproduce a crash or assertion: *
 **************************************/

// 1. grep tryIt LOGFILE | grep -v "function tryIt" | pbcopy
// 2. Paste the result between "ddbegin" and "ddend", replacing "start();"
// 3. Run Lithium to remove unnecessary lines between "ddbegin" and "ddend".
// DDBEGIN
start();
// DDEND


// 3. Run it.

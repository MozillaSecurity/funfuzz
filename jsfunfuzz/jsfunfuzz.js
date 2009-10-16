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
 * Portions created by the Initial Developer are Copyright (C) 2006-2009
 * the Initial Developer. All Rights Reserved.
 *
 * Contributor(s):
 * Gary Kwong
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
var ENGINE_SPIDERMONKEY_TRUNK = 1; // also 1.9.1 and tracemonkey branch
var ENGINE_SPIDERMONKEY_MOZ_1_9_0 = 2;
var ENGINE_SPIDERMONKEY_MOZ_1_8 = 3;
var ENGINE_JAVASCRIPTCORE = 4;

var engine = ENGINE_UNKNOWN;
var jsshell = (typeof window == "undefined");
if (jsshell) {
  dump = print;
  dumpln = print;
  printImportant = function(s) { dumpln("***"); dumpln(s); }
  if (typeof line2pc == "function") {

    if (typeof snarf == "function")
      engine = ENGINE_SPIDERMONKEY_TRUNK;
    else if (typeof countHeap == "function")
      engine = ENGINE_SPIDERMONKEY_MOZ_1_9_0
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
  } else if (navigator.userAgent.indexOf("Gecko") != -1 && navigator.userAgent.indexOf("rv:1.9.0") != -1) {
    engine = ENGINE_SPIDERMONKEY_MOZ_1_9_0;
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

var haveUsefulDis = engine == ENGINE_SPIDERMONKEY_TRUNK && typeof dis == "function" && typeof dis(function(){}) == "string";

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
else if (engine == ENGINE_SPIDERMONKEY_MOZ_1_9_0)
  printImportant("Targeting SpiderMonkey / Gecko (Mozilla 1.9.0 branch).");
else if (engine == ENGINE_SPIDERMONKEY_TRUNK)
  printImportant("Targeting SpiderMonkey / Gecko (trunk).");
else if (engine == ENGINE_JAVASCRIPTCORE)
  printImportant("Targeting JavaScriptCore / WebKit.");

function printAndStop(s)
{
  printImportant(s)
  if (jsshell) {
    print("jsfunfuzz stopping due to above error!"); // Magic string that jsunhappy.py looks for
    quit();
  }
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
      && !( code.match( /const.*arguments/ ))        // avoid bug 355480
      && !( code.match( /var.*arguments/ ))          // avoid bug 355480
      && !( code.match( /let.*arguments/ ))          // avoid bug 355480
      && !( code.match( /let/ ))   // avoid bug 462309 :( :( :(
      && !( code.match( /function.*\:.*arguments/ ))   // avoid bug 496985
      && !( code.match( /\{.*\:.*\}.*\=.*/ ) && code.indexOf("const") != -1)    // avoid bug 492010
      && !( code.match( /\{.*\:.*\}.*\=.*/ ) && code.indexOf("function") != -1) // avoid bug 492010
      && !( code.match( /if.*function/ ) && code.indexOf("const") != -1)        // avoid bug 355980 *errors*
      ,
  
    // Exclude things here if decompiling returns something incorrect or non-canonical, but that will compile.
    checkForMismatch: true
      && !( code.match( /const.*if/ ))               // avoid bug 352985
      && !( code.match( /if.*const/ ))               // avoid bug 352985
      && !( code.match( /with.*try.*function/ ))     // avoid bug 418285
      && !( code.match( /if.*try.*function/ ))       // avoid bug 418285
      && !( code.match( /\[.*\].*\=.*\[.*\,/ ))      // avoid bug 355051
      && !( code.match( /\{.*\}.*\=.*\[.*\,/ ))      // avoid bug 355051 where empty {} becomes []
      && !( code.match( /\[.*\].*\=.*\[.*\yield/ ))  // avoid bug 498934
      && !( code.match( /\{.*\}.*\=.*\[.*\yield/ ))  // avoid bug 498934 where empty {} becomes []
      && !( code.match( /\?.*\?/ ))        // avoid bug 475895
      && !( code.match( /if.*function/ ))              // avoid bug 355980 *changes*
      && !( code.match( /new.*eval/ ))               // avoid bug 521456
      && (code.indexOf("-0") == -1)        // constant folding isn't perfect
      && (code.indexOf("-1") == -1)        // constant folding isn't perfect
      && (code.indexOf("default") == -1)   // avoid bug 355509
      && (code.indexOf("delete") == -1)    // avoid bug 352027, which won't be fixed for a while :(
      && (code.indexOf("const") == -1)     // avoid bug 352985 and bug 355480 :(
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
      && !( code.match( /\@.*\:\:/ ))   // avoid bug 381197 harder than above
      && !( code.match( /for.*in.*for.*in/ ))   // avoid bug 475985
    ,  
    
    checkForExtraParens: true
      && !code.match( /\(.*for.*\(.*in.*\).*\)/ )  // ignore bug 381213, and unfortunately anything with genexps
      && !code.match( /if.*\(.*=.*\)/)      // ignore extra parens added to avoid strict warning
      && !code.match( /while.*\(.*=.*\)/)   // ignore extra parens added to avoid strict warning
      && !code.match( /\?.*\=/)             // ignore bug 475893
    ,
    
    allowExec: unlikelyToHang(code)
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


function whatToTestSpidermonkey190Branch(code)
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
      && !( code.match( /\?.*\?/ ))        // avoid bug 475895
      && !( code.match( /for.*;.*;/ ))               // avoid wackiness related to bug 461269
      && !( code.match( /new.*\?/ ))                 // avoid bug 476210
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
      && !( code.match( /\@.*\:\:/ ))   // avoid bug 381197 harder than above
      && !( code.match( /\(.*\?.*\:.*\).*\(.*\)/ ))   // avoid bug 475899
      && !( code.match( /for.*in.*for.*in/ ))   // avoid bug 475985
    ,  
    
    checkForExtraParens: true
      && !code.match( /\(.*for.*\(.*in.*\).*\)/ )  // ignore bug 381213, and unfortunately anything with genexps
      && !code.match( /if.*\(.*=.*\)/)      // ignore extra parens added to avoid strict warning
      && !code.match( /while.*\(.*=.*\)/)   // ignore extra parens added to avoid strict warning
      && !code.match( /\?.*\=/)             // ignore bug 475893
    ,
    
    allowExec: unlikelyToHang(code)
      && code.indexOf("finally")  == -1 // avoid bug 380018 and bug 381107 :(
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
else if (engine == ENGINE_SPIDERMONKEY_MOZ_1_9_0)
  whatToTest = whatToTestSpidermonkey190Branch;
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
function totallyRandom(d, b) {
  d = d + (rnd(5) - 2); // can increase!!

  return (rndElt(allMakers))(d, b);
}

function init()
{
  for (var f in this)
    if (f.indexOf("make") == 0 && typeof this[f] == "function")
      allMakers.push(this[f]);
}

function testEachMaker()
{
  for each (var f in allMakers) {
    dumpln("");
    dumpln(f.name);
    dumpln("==========");
    dumpln("");
    for (var i = 0; i < 100; ++i) {
      try {
        dumpln(f(8, ["A", "B"]));
      } catch(e) {
        dumpln("");
        dumpln(uneval(e));
        dumpln(e.stack);
        dumpln("");
      }
    }
    dumpln("");
  }
}

function start()
{
  init();

  count = 0;

  if (jsshell) {
    // If another script specified a "maxRunTime" argument, use it; otherwise, run forever
    var MAX_TOTAL_TIME = (this.maxRunTime) || (Infinity);
    var startTime = new Date();

    do {
      testOne();
      var elapsed1 = new Date() - lastTime;
      if (elapsed1 > 1000) {
        print("That took " + elapsed1 + "ms!");
      }
      var lastTime = new Date();
    } while(lastTime - startTime < MAX_TOTAL_TIME);
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
  var dumpEachSeed = false; // Can be set to true if makeStatement has side effects, such as crashing, so you have to reduce "the hard way".
  ++count;
  // Split this string across two source strings to ensure that if a 
  // generated function manages to output the entire jsfunfuzz source, 
  // that output won't match the grep command.
  var grepforme = "/*F";
  grepforme += "RC*/"

  if (dumpEachSeed) {
    // More complicated, but results in a much shorter script, making SpiderMonkey happier.
    var MTA = uneval(rnd.fuzzMT.export_mta());
    var MTI = rnd.fuzzMT.export_mti();
    if (MTA != rnd.lastDumpedMTA) {
      dumpln(grepforme + "rnd.fuzzMT.import_mta(" + MTA + ");");
      rnd.lastDumpedMTA = MTA;
    }
    dumpln(grepforme + "rnd.fuzzMT.import_mti(" + MTI + "); void (makeStatement(8));");
  }

  var code = makeStatement(10, ["x"]);
  
//  if (rnd(10) == 1) {
//    var dp = "/*infloop-deParen*/" + rndElt(deParen(code));
//    if (dp)
//      code = dp;
//  }
  dumpln(grepforme + "count=" + count + "; tryItOut(" + uneval(code) + ");");

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

  // regexps can't match across lines, so replace whitespace with spaces.
  var wtt = whatToTest(code.replace(/\s/g, " "));

  if (!wtt.allowParse)
    return;
    
  if (count % 20 == 1) {
    if (wtt.allowExec) {
      try {
        print("Plain eval");
        eval(code);
      } catch(e) {
        print(errorToString(e));
      }
      tryEnsureSanity();
    }
    return;
  }

  var f = tryCompiling(code, wtt.allowExec);

  optionalTests(f, code, wtt);

  if (f && wtt.allowDecompile) {
    tryRoundTripStuff(f, code, wtt);
    if (haveUsefulDis && wtt.checkRecompiling && wtt.checkForMismatch && wtt.checkDisassembly)
      checkRoundTripDisassembly(f, code, wtt);
  }

  if (f && wtt.allowExec) {
    if (code.indexOf("\n") == -1 && code.indexOf("\r") == -1 && code.indexOf("\f") == -1 && code.indexOf("\0") == -1 && code.indexOf("\u2028") == -1 && code.indexOf("\u2029") == -1 && code.indexOf("<--") == -1 && code.indexOf("-->") == -1 && code.indexOf("//") == -1) {
      if (code.indexOf("<") == -1 || code.indexOf(">") == -1) { // avoid bug 470316
        var cookie1 = "/*F";
        var cookie2 = "CM*/";
        dumpln(cookie1 + cookie2 + " try { (function(){ " + code + "})() } catch(e) { }");
      }
    }
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
    // bug 465908 and other e4x uneval nonsense make this show lots of false positives
    // checkErrorMessage(err, code);
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
  try {
    // The script might have turned on gczeal.  Turn it back off right away to avoid slowness.
    if ("gczeal" in this)
      gczeal(0);
  
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
  } catch(e) {
    printImportant("tryEnsureSanity failed: " + e);
  }

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
  var fs, g;
  try {
    fs = "" + f;
  } catch(e) { reportRoundTripIssue("Round-trip with implicit toString: can't toString", code, null, null, errorToString(e)); return; }

  checkForCookies(fs);
  
  if (fs == "[object Function]" && engine == ENGINE_SPIDERMONKEY_MOZ_1_8) {
    print("Skipping round-trip test -- bug 432075");
    return;
  }

  if (wtt.checkRecompiling) {
    try {
      g = eval("(" + fs + ")");
      var gs = "" + g;
      if (wtt.checkForMismatch && fs != gs) {
        reportRoundTripIssue("Round-trip with implicit toString", code, fs, gs, "mismatch");
        wtt.checkForMismatch = false;
      }
    } catch(e) {
      reportRoundTripIssue("Round-trip with implicit toString: error", code, fs, gs, errorToString(e));
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
  
  if (engine == ENGINE_SPIDERMONKEY_MOZ_1_9_0 && e.indexOf("invalid object initializer") != -1) {
    dumpln("Ignoring bug 452561.");
    return;
  }
  
  if (e.indexOf("illegal XML character") != -1) {
    dumpln("Ignoring bug 355674.");
    return;
  }
  
  if (engine == ENGINE_SPIDERMONKEY_MOZ_1_9_0 && e.indexOf("missing ; after for-loop condition") != -1) {
    dumpln("Looks like bug 460504.");
    return;
  }
  
  if (fs && gs && fs.replace(/'/g, "\"") == gs.replace(/'/g, "\"")) {
    dumpln("Ignoring quote mismatch (bug 346898).");
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
      &&  uo.indexOf(",]") == -1                           // avoid  bug 334628 / bug 379525?
      &&  uo.indexOf("[function") == -1                    // avoid  bug 380379?
      &&  uo.indexOf("[(function") == -1                   // avoid  bug 380379?
      && !uowlb.match(/new.*Error/)                        // ignore bug 380578
      && !uowlb.match(/<.*\/.*>.*<.*\/.*>/)                // ignore bug 334628
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
  code = code.replace(/\n/g, " ").replace(/\r/g, " "); // regexps can't match across lines

  var uf = "" + f;

  // numbers get more parens than they need
  if (uf.match(/\(\d/)) return;

  if (uf.indexOf("(<") != -1) return; // bug 381204
  if (uf.indexOf(".(") != -1) return; // bug 381207
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


/*********************************
 * SPIDERMONKEY DISASSEMBLY TEST *
 *********************************/

// Finds decompiler bugs and bytecode inefficiencies by complaining when a round trip
// through the decompiler changes the bytecode.
function checkRoundTripDisassembly(f, code, wtt)
{
  if (code.indexOf("[@") != -1 || code.indexOf("*::") != -1 || code.indexOf("::*") != -1 || code.match(/\[.*\*/)) {
    dumpln("checkRoundTripDisassembly: ignoring bug 475859");
    return;
  }
  
  if (code.indexOf("=") != -1 && code.indexOf("const") != -1) {
    dumpln("checkRoundTripDisassembly: ignoring function with const and assignment, because that's boring.");
    return;
  }
  
  var uf = uneval(f);

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
  if (df.indexOf("trap") != -1) {
    print("checkRoundTripDisassembly: trapped");
    return;
  }

  var dg = dis(g);

  if (df == dg) {
    // Happy!
    if (wtt.allowExec)
      trapCorrectnessTest(f);
    return;
  }

  if (dg.indexOf("newline") != -1) {
    // Really should just ignore these lines, instead of bailing...
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
      if (dfl[i].indexOf("pcdelta") != -1 && dgl[i].indexOf("pcdelta") != -1) {
        print("checkRoundTripDisassembly: pcdelta changed, who cares? (bug 475908)");
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



/*****************************
 * SPIDERMONKEY TRAP TESTING *
 *****************************/


function getBytecodeOffsets(f)
{
  var disassembly = dis(f);
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

    // The opcodes |tableswitch| and |lookupswitch| add indented lists,
    // which we want to ignore.
    var c = lines[i].charCodeAt(0);
    if (!(0x30 <= c && c <= 0x39))
      continue;

    var op = lines[i].substr(8).split(" ")[0]; // used only for avoiding known bugs
    var offset = parseInt(lines[i], 10);
    offsets.push({ offset: offset, op: op });
    if (op == "getter" || op == "setter") {
      ++i; // skip the next opcode per bug 476073 comment 4
    }
  }
  
  return offsets;
}

function trapCorrectnessTest(f)
{
  var uf = uneval(f);
  
  print("trapCorrectnessTest...");
  var offsets = getBytecodeOffsets(f);
  var prefix = "var fff = " + f + "; ";
  var r1 = sandboxResult(prefix + "fff();");
  for (var i = 0; i < offsets.length; ++i) {
    var offset = offsets[i].offset;
    var op = offsets[i].op;
    // print(offset + " " + op);

    var trapStr = "trap(fff, " + offset + ", ''); ";
    var r2 = sandboxResult(prefix + trapStr + " fff();");

    if (r1 != r2) {
      if (r1.indexOf("TypeError") != -1 && r2.indexOf("TypeError") != -1) {
        // Why does this get printed multiple times???
        // count=6544; tIO("var x; x.y;");
        print("A TypeError changed. Might be bug 476088.");
        continue;
      }

      print("Adding a trap changed the result!");
      print(f);
      print(r1);
      print(trapStr);
      print(r2);
      printAndStop(":(");
    }
  }
  //print("Happy: " + f + r1);
}

function sandboxResult(code)
{
  // Use sandbox to isolate side-effects.
  // This might be wrong in cases where the sandbox manages to return objects with getters and stuff!
  var result;
  try {
    // result = evalcx(code, {trap:trap, print:print}); // WRONG
    var sandbox = evalcx("");
    sandbox.trap = trap;
    sandbox.print = print;
    sandbox.dis = dis;
    result = evalcx(code, sandbox);
  } catch(e) {
    result = "Error: " + errorToString(e);
  }
  return "" + result;
}

// This tests two aspects of trap:
// 1) put a trap in a random place; does decompilation get horked?
// 2) traps that do things
// These should probably be split into different tests.
function spiderMonkeyTrapTest(f, code, wtt)
{
  var offsets = getBytecodeOffsets(f);

  if ("trap" in this) {

    // Save for trap      
    //if (wtt.allowExec && count % 2 == 0) {
      //nextTrapCode = code;
    //  return;
    //}

    // Use trap

    if (verbose)
      dumpln("About to try the trap test.");

    var ode;
    if (wtt.allowDecompile)
      ode = "" + f;
      
    //if (nextTrapCode) {
    //  trapCode = nextTrapCode;
    //  nextTrapCode = null;
    //  print("trapCode = " + simpleSource(trapCode));
    //} else {
      trapCode = "print('Trap hit!')";
    //}


    trapOffset = offsets[count % offsets.length].offset;
    print("trapOffset: " + trapOffset);
    if (!(trapOffset > -1)) {
      print(dis(f));
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
  
  if (0 && f && haveUsefulDis) {
    spiderMonkeyTrapTest(f, code, wtt);
  }

  if (0 && f && wtt.allowExec && engine == ENGINE_SPIDERMONKEY_TRUNK) {
    simpleDVGTest(code);
    tryEnsureSanity();
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
	
    this.export_state = function() { return [mt, mti]; };
    this.import_state = function(s) { mt = s[0]; mti = s[1]; };
    this.export_mta = function() { return mt; };
    this.import_mta = function(_mta) { mt = _mta };
    this.export_mti = function() { return mti; };
    this.import_mti = function(_mti) { mti = _mti; }

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


function errorstack()
{
  print("EEE");
  try { [].qwerty.qwerty } catch(e) { print(e.stack) }
}

function rndElt(a)
{ 
  if (typeof a == "string") {
    dumpln("String passed to rndElt: " + a);
    errorstack();
  }
    
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
  if (rnd(1700) == 0)
    return totallyRandom(2, []);
  
  var torture = (rnd(1700) == 57);
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

function makeStatement(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (d < 6 && rnd(3) == 0)
    return makePrintStatement(d, b);
  
  if (d < rnd(8)) // frequently for small depth, infrequently for large depth
    return makeLittleStatement(d, b);

  d = rnd(d); // !
  
  return (rndElt(statementMakers))(d, b)
}

var varBinder = ["var ", "let ", "const ", ""];
var varBinderFor = ["var ", "let ", ""]; // const is a syntax error in for loops

// The reason there are several types of loops here is to create different
// types of scripts without introducing infinite loops.

function makeOpaqueIdiomaticLoop(d, b)
{
  var reps = 1 + rnd(7);
  var vHidden = uniqueVarName();
  return ("/*oLoop*/for (" + rndElt(varBinderFor) + "x = 0; x < " + reps + "; ++x) ").replace(/x/g, vHidden) + 
      makeStatement(d - 2, b);
}

function makeTransparentIdiomaticLoop(d, b)
{
  var reps = 1 + rnd(7);
  var vHidden = uniqueVarName();
  var vVisible = makeNewId(d, b);
  return ("/*vLoop*/for (" + rndElt(varBinderFor) + "x = 0; x < " + reps + "; ++x)").replace(/x/g, vHidden) + 
    " { " + 
      rndElt(varBinder) + vVisible + " = " + vHidden + "; " +
      makeStatement(d - 2, b.concat([vVisible])) +
    " } "
}

function makeBranchUnstableLoop(d, b)
{
  var reps = 1 + rnd(24);
  var v = uniqueVarName();
  var mod = rnd(5) + 2;
  var target = rnd(mod);
  var loopHead = ("/*bLoop*/for (var x = 0; x < " + reps + "; ++x)").replace(/x/g, v);
  return loopHead + " { " + 
    "if (" + v + " % " + mod + " == " + target + ") { " + makeStatement(d - 2, b) + " } " +
    "else { " + makeStatement(d - 2, b) + " } " +
    " } "
}

function makeTypeUnstableLoop(d, b) {
  var a = makeMixedTypeArray(d, b);
  var v = makeNewId(d, b);
  var bv = b.concat([v]);
  return "/*tLoop*/for each (let " + v + " in " + a + ") { " + makeStatement(d - 2, bv) + " }";
}

function weighted(wa)
{
  var a = [];
  for (var i = 0; i < wa.length; ++i) {
    for (var j = 0; j < wa[i].w; ++j) {
      a.push(wa[i].fun);
    }
  }
  return a;
}
  
var statementMakers = weighted([

  // Any two statements in sequence
  { w: 4, fun: function(d, b) { return cat([makeStatement(d, b), makeStatement(d, b)]); } },
  { w: 4, fun: function(d, b) { return cat([makeStatement(d - 1, b), "\n", makeStatement(d - 1, b), "\n"]); } },

  // Stripping semilcolons.  What happens if semicolons are missing?  Especially with line breaks used in place of semicolons (semicolon insertion).
  { w: 1, fun: function(d, b) { return cat([stripSemicolon(makeStatement(d, b)), "\n", makeStatement(d, b)]); } },
  { w: 1, fun: function(d, b) { return cat([stripSemicolon(makeStatement(d, b)), "\n"                   ]); } },
  { w: 1, fun: function(d, b) { return stripSemicolon(makeStatement(d, b)); } }, // usually invalid, but can be ok e.g. at the end of a block with curly braces

  // Simple variable declarations, followed (or preceded) by statements using those variables
  { w: 4, fun: function(d, b) { var v = makeNewId(d, b); return cat([rndElt(varBinder), v, " = ", makeExpr(d, b), ";", makeStatement(d - 1, b.concat([v]))]); } },
  { w: 4, fun: function(d, b) { var v = makeNewId(d, b); return cat([makeStatement(d - 1, b.concat([v])), rndElt(varBinder), v, " = ", makeExpr(d, b), ";"]); } },

  // Complex variable declarations, e.g. "const [a,b] = [3,4];"
  { w: 1, fun: function(d, b) { return cat([rndElt(varBinder), makeLetHead(d, b), ";", makeStatement(d - 1, b)]); } },
  
  // Blocks
  { w: 2, fun: function(d, b) { return cat(["{", makeStatement(d, b), " }"]); } },
  { w: 2, fun: function(d, b) { return cat(["{", makeStatement(d - 1, b), makeStatement(d - 1, b), " }"]); } },

  // "with" blocks
  { w: 2, fun: function(d, b) {                          return cat([maybeLabel(), "with", "(", makeExpr(d, b), ")",                    makeStatementOrBlock(d, b)]);             } },
  { w: 2, fun: function(d, b) { var v = makeNewId(d, b); return cat([maybeLabel(), "with", "(", "{", v, ": ", makeExpr(d, b), "}", ")", makeStatementOrBlock(d, b.concat([v]))]); } },

  // C-style "for" loops
  // Two kinds of "for" loops: one with an expression as the first part, one with a var or let binding 'statement' as the first part.
  // I'm not sure if arbitrary statements are allowed there; I think not.
  { w: 1, fun: function(d, b) {                          return "/*infloop*/" + cat([maybeLabel(), "for", "(", makeExpr(d, b), "; ", makeExpr(d, b), "; ", makeExpr(d, b), ") ", makeStatementOrBlock(d, b)]); } }, 
  { w: 1, fun: function(d, b) { var v = makeNewId(d, b); return "/*infloop*/" + cat([maybeLabel(), "for", "(", rndElt(varBinderFor), v,                                                    "; ", makeExpr(d, b), "; ", makeExpr(d, b), ") ", makeStatementOrBlock(d, b.concat([v]))]); } }, 
  { w: 1, fun: function(d, b) { var v = makeNewId(d, b); return "/*infloop*/" + cat([maybeLabel(), "for", "(", rndElt(varBinderFor), v, " = ", makeExpr(d, b),                             "; ", makeExpr(d, b), "; ", makeExpr(d, b), ") ", makeStatementOrBlock(d, b.concat([v]))]); } }, 
  { w: 1, fun: function(d, b) {                          return "/*infloop*/" + cat([maybeLabel(), "for", "(", rndElt(varBinderFor), makeDestructuringLValue(d, b), " = ", makeExpr(d, b), "; ", makeExpr(d, b), "; ", makeExpr(d, b), ") ", makeStatementOrBlock(d, b)]); } }, 
  
  // Various types of "for" loops, specially set up to test tracing, carefully avoiding infinite loops
  { w: 6, fun: makeTransparentIdiomaticLoop },
  { w: 6, fun: makeOpaqueIdiomaticLoop },
  { w: 6, fun: makeBranchUnstableLoop },
  { w: 8, fun: makeTypeUnstableLoop }, 

  // "for..in" loops
  // arbitrary-LHS marked as infloop because
  // -- for (key in obj)
  { w: 1, fun: function(d, b) {                          return "/*infloop*/" + cat([maybeLabel(), "for", "(", rndElt(varBinderFor), makeForInLHS(d, b), " in ", makeExpr(d - 2, b), ") ", makeStatementOrBlock(d, b)]); } },
  { w: 1, fun: function(d, b) { var v = makeNewId(d, b); return                 cat([maybeLabel(), "for", "(", rndElt(varBinderFor), v,                  " in ", makeExpr(d - 2, b), ") ", makeStatementOrBlock(d, b.concat([v]))]); } },
  // -- for (key in generator())
  { w: 1, fun: function(d, b) {                          return "/*infloop*/" + cat([maybeLabel(), "for", "(", rndElt(varBinderFor), makeForInLHS(d, b), " in ", "(", "(", makeFunction(d, b), ")", "(", makeExpr(d, b), ")", ")", ")", makeStatementOrBlock(d, b)]); } },
  { w: 1, fun: function(d, b) { var v = makeNewId(d, b); return                 cat([maybeLabel(), "for", "(", rndElt(varBinderFor), v,                  " in ", "(", "(", makeFunction(d, b), ")", "(", makeExpr(d, b), ")", ")", ")", makeStatementOrBlock(d, b.concat([v]))]); } },
  // -- for each (value in obj)
  { w: 1, fun: function(d, b) {                          return "/*infloop*/" + cat([maybeLabel(), " for ", " each", "(", rndElt(varBinderFor), makeLValue(d, b), " in ", makeExpr(d - 2, b), ") ", makeStatementOrBlock(d, b)]); } },
  { w: 1, fun: function(d, b) { var v = makeNewId(d, b); return                 cat([maybeLabel(), " for ", " each", "(", rndElt(varBinderFor), v,                " in ", makeExpr(d - 2, b), ") ", makeStatementOrBlock(d, b.concat([v]))]); } },
  
  // Modify something during a loop -- perhaps the thing being looped over
  // Since we use "let" to bind the for-variables, and only do wacky stuff once, I *think* this is unlikely to hang.
//  function(d, b) { return "let forCount = 0; for (let " + makeId(d, b) + " in " + makeExpr(d, b) + ") { if (forCount++ == " + rnd(3) + ") { " + makeStatement(d - 1, b) + " } }"; },

  // Hoisty "for..in" loops.  I don't know why this construct exists, but it does, and it hoists the initial-value expression above the loop.
  // With "var" or "const", the entire thing is hoisted.
  // With "let", only the value is hoisted, and it can be elim'ed as a useless statement.
  // The first form could be an infinite loop because of "for (x.y in x)" with e4x.
  // The last form is specific to JavaScript 1.7 (only).
  { w: 1, fun: function(d, b) {                       return "/*infloop*/" +         cat([maybeLabel(), "for", "(", rndElt(varBinderFor), makeId(d, b),         " = ", makeExpr(d, b), " in ", makeExpr(d - 2, b), ") ", makeStatementOrBlock(d, b)]); } },
  { w: 1, fun: function(d, b) { var v = makeNewId(d, b);                      return cat([maybeLabel(), "for", "(", rndElt(varBinderFor), v,                    " = ", makeExpr(d, b), " in ", makeExpr(d - 2, b), ") ", makeStatementOrBlock(d, b.concat([v]))]); } },
  { w: 1, fun: function(d, b) { var v = makeNewId(d, b), w = makeNewId(d, b); return cat([maybeLabel(), "for", "(", rndElt(varBinderFor), "[", v, ", ", w, "]", " = ", makeExpr(d, b), " in ", makeExpr(d - 2, b), ") ", makeStatementOrBlock(d, b.concat([v, w]))]); } },

  // do..while
  { w: 1, fun: function(d, b) { return cat([maybeLabel(), "while((", makeExpr(d, b), ") && 0)" /*don't split this, it's needed to avoid marking as infloop*/, makeStatementOrBlock(d, b)]); } },
  { w: 1, fun: function(d, b) { return "/*infloop*/" + cat([maybeLabel(), "while", "(", makeExpr(d, b), ")", makeStatementOrBlock(d, b)]); } },
  { w: 1, fun: function(d, b) { return cat([maybeLabel(), "do ", makeStatementOrBlock(d, b), " while((", makeExpr(d, b), ") && 0)" /*don't split this, it's needed to avoid marking as infloop*/, ";"]); } },
  { w: 1, fun: function(d, b) { return "/*infloop*/" + cat([maybeLabel(), "do ", makeStatementOrBlock(d, b), " while", "(", makeExpr(d, b), ");"]); } },

  // Switch statement
  { w: 3, fun: function(d, b) { return cat([maybeLabel(), "switch", "(", makeExpr(d, b), ")", " { ", makeSwitchBody(d, b), " }"]); } },

  // "let" blocks, with bound variable used inside the block
  { w: 2, fun: function(d, b) { var v = makeNewId(d, b); return cat(["let ", "(", v, ")", " { ", makeStatement(d, b.concat([v])), " }"]); } },

  // "let" blocks, with and without multiple bindings, with and without initial values
  { w: 2, fun: function(d, b) { return cat(["let ", "(", makeLetHead(d, b), ")", " { ", makeStatement(d, b), " }"]); } },

  // Conditionals, perhaps with 'else if' / 'else'
  { w: 1, fun: function(d, b) { return cat([maybeLabel(), "if(", makeExpr(d, b), ") ", makeStatementOrBlock(d, b)]); } },
  { w: 1, fun: function(d, b) { return cat([maybeLabel(), "if(", makeExpr(d, b), ") ", makeStatementOrBlock(d - 1, b), " else ", makeStatementOrBlock(d - 1, b)]); } },
  { w: 1, fun: function(d, b) { return cat([maybeLabel(), "if(", makeExpr(d, b), ") ", makeStatementOrBlock(d - 1, b), " else ", " if ", "(", makeExpr(d, b), ") ", makeStatementOrBlock(d - 1, b)]); } },
  { w: 1, fun: function(d, b) { return cat([maybeLabel(), "if(", makeExpr(d, b), ") ", makeStatementOrBlock(d - 1, b), " else ", " if ", "(", makeExpr(d, b), ") ", makeStatementOrBlock(d - 1, b), " else ", makeStatementOrBlock(d - 1, b)]); } },

  // A tricky pair of if/else cases.
  // In the SECOND case, braces must be preserved to keep the final "else" associated with the first "if".
  { w: 1, fun: function(d, b) { return cat([maybeLabel(), "if(", makeExpr(d, b), ") ", "{", " if ", "(", makeExpr(d, b), ") ", makeStatementOrBlock(d - 1, b), " else ", makeStatementOrBlock(d - 1, b), "}"]); } },
  { w: 1, fun: function(d, b) { return cat([maybeLabel(), "if(", makeExpr(d, b), ") ", "{", " if ", "(", makeExpr(d, b), ") ", makeStatementOrBlock(d - 1, b), "}", " else ", makeStatementOrBlock(d - 1, b)]); } },
  
  // Expression statements
  { w: 5, fun: function(d, b) { return cat([makeExpr(d, b), ";"]); } },
  { w: 5, fun: function(d, b) { return cat(["(", makeExpr(d, b), ")", ";"]); } },

  // Exception-related statements :)
  { w: 6, fun: function(d, b) { return makeExceptionyStatement(d - 1, b) + makeExceptionyStatement(d - 1, b); } },
  { w: 7, fun: function(d, b) { return makeExceptionyStatement(d, b); } },

  // Labels. (JavaScript does not have goto, but it does have break-to-label and continue-to-label).
  { w: 1, fun: function(d, b) { return cat(["L", ": ", makeStatementOrBlock(d, b)]); } },
  
  // Functions which are called?
  // Tends to trigger OOM bugs
  // function(d, b) { return cat(["/*hhh*/function ", "x", "(", ")", "{", makeStatement(d, b), "}", " ", "x", "(", makeActualArgList(d, b), ")"]); }
]);

function makePrintStatement(d, b)
{
  if (rnd(2))
    return "print(" + rndElt(b) + ");";
  else
    return "print(" + makeExpr(d, b) + ");";
}


function maybeLabel()
{
  if (rnd(4) == 1)
    return cat([rndElt(["L", "M"]), ":"]);
  else
    return "";
}


function uniqueVarName()
{
  // Make a random variable name.
  var i, s = "";
  for (i = 0; i < 6; ++i)
    s += String.fromCharCode(97 + rnd(26)); // a lowercase english letter
  return s;
}



function makeSwitchBody(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

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
        output += "case " + (rnd(2) ? rnd(10) : makeExpr(d, b)) + ": ";
      }

      haveSomething = true;
    }
    
    // Might want a statement.
    if (rnd(2))
      output += makeStatement(d, b)

    // Might want to break, or might want to fall through.
    if (rnd(2))
      output += "break; ";
    
    if (rnd(2))
      --d;

  } while (d && rnd(5));
  
  return output;
}

function makeLittleStatement(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  d = d - 1;

  if (rnd(4) == 1)
    return makeStatement(d, b);
  
  return (rndElt(littleStatementMakers))(d, b);
}

var littleStatementMakers = 
[
  // Tiny
  function(d, b) { return cat([";"]); }, // e.g. empty "if" block
  function(d, b) { return cat(["{", "}"]); }, // e.g. empty "if" block
  function(d, b) { return cat([""]); },

  // Force garbage collection
  function(d, b) { return "gc()"; },
  
  // Throw stuff.
  function(d, b) { return cat(["throw ", makeExpr(d, b), ";"]); },

  // Break/continue [to label].
  function(d, b) { return cat([rndElt(["continue", "break"]), " ", rndElt(["L", "M", "", ""]), ";"]); },

  // Named and unnamed functions (which have different behaviors in different places: both can be expressions,
  // but unnamed functions "want" to be expressions and named functions "want" to be special statements)
  function(d, b) { return makeFunction(d, b); },
  
  // Return, yield
  function(d, b) { return cat(["return ", makeExpr(d, b), ";"]); },
  function(d, b) { return "return;"; }, // return without a value is allowed in generators; return with a value is not.
  function(d, b) { return cat(["yield ", makeExpr(d, b), ";"]); }, // note: yield can also be a left-unary operator, or something like that
  function(d, b) { return "yield;"; },

  // Expression statements
  function(d, b) { return cat([makeExpr(d, b), ";"]); },
  function(d, b) { return cat([makeExpr(d, b), ";"]); },
  function(d, b) { return cat([makeExpr(d, b), ";"]); },
  function(d, b) { return cat([makeExpr(d, b), ";"]); },
  function(d, b) { return cat([makeExpr(d, b), ";"]); },
  function(d, b) { return cat([makeExpr(d, b), ";"]); },
  function(d, b) { return cat([makeExpr(d, b), ";"]); },
  function(d, b) { return cat(["(", makeExpr(d, b), ")", ";"]); },
  function(d, b) { return cat(["(", makeExpr(d, b), ")", ";"]); },
  function(d, b) { return cat(["(", makeExpr(d, b), ")", ";"]); },
  function(d, b) { return cat(["(", makeExpr(d, b), ")", ";"]); },
  function(d, b) { return cat(["(", makeExpr(d, b), ")", ";"]); },
  function(d, b) { return cat(["(", makeExpr(d, b), ")", ";"]); },
  function(d, b) { return cat(["(", makeExpr(d, b), ")", ";"]); },
  
  // Turn on gczeal in the middle of something
  function(d, b) { return "gczeal(" + makeZealLevel() + ")" + ";"; }
];


// makeStatementOrBlock exists because often, things have different behaviors depending on where there are braces.
// for example, if braces are added or removed, the meaning of "let" can change.
function makeStatementOrBlock(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  return (rndElt(statementBlockMakers))(d - 1, b);
}

var statementBlockMakers = [
  function(d, b) { return makeStatement(d, b); },
  function(d, b) { return makeStatement(d, b); },
  function(d, b) { return cat(["{", makeStatement(d, b), " }"]); },
  function(d, b) { return cat(["{", makeStatement(d - 1, b), makeStatement(d - 1, b), " }"]); },
]


// Extra-hard testing for try/catch/finally and related things.

function makeExceptionyStatement(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  d = d - 1;
  if (d < 1)
    return makeLittleStatement(d, b);

  return (rndElt(exceptionyStatementMakers))(d, b);
}

var exceptionyStatementMakers = [
  function(d, b) { return makeTryBlock(d, b); },

  function(d, b) { return makeStatement(d, b); },
  function(d, b) { return makeLittleStatement(d, b); },

  function(d, b) { return "return;" }, // return without a value can be mixed with yield
  function(d, b) { return cat(["return ", makeExpr(d, b), ";"]); },
  function(d, b) { return cat(["yield ", makeExpr(d, b), ";"]); },
  function(d, b) { return cat(["throw ", makeId(d, b), ";"]); },
  function(d, b) { return "throw StopIteration;"; },
  function(d, b) { return "this.zzz.zzz;"; }, // throws; also tests js_DecompileValueGenerator in various locations
  function(d, b) { return cat([makeId(d, b), " = ", makeId(d, b), ";"]); },
  function(d, b) { return cat([makeLValue(d, b), " = ", makeId(d, b), ";"]); },

  // Iteration uses StopIteration internally.
  // Iteration is also useful to test because it asserts that there is no pending exception.
  function(d, b) { var v = makeNewId(d, b); return "for(let " + v + " in []);"; }, 
  function(d, b) { var v = makeNewId(d, b); return "for(let " + v + " in " + makeMixedTypeArray(d, b) + ") " + makeExceptionyStatement(d, b.concat([v])); }, 
  
  // Brendan says these are scary places to throw: with, let block, lambda called immediately in let expr.
  // And I think he was right.
  function(d, b) { return "with({}) "   + makeExceptionyStatement(d, b);         },
  function(d, b) { return "with({}) { " + makeExceptionyStatement(d, b) + " } "; },
  function(d, b) { var v = makeNewId(d, b); return "let(" + v + ") { " + makeExceptionyStatement(d, b.concat([v])) + "}"; },
  function(d, b) { var v = makeNewId(d, b); return "let(" + v + ") ((function(){" + makeExceptionyStatement(d, b.concat([v])) + "})());" },
  function(d, b) { return "let(" + makeLetHead(d, b) + ") { " + makeExceptionyStatement(d, b) + "}"; },
  function(d, b) { return "let(" + makeLetHead(d, b) + ") ((function(){" + makeExceptionyStatement(d, b) + "})());" },

  // Commented out due to causing too much noise on stderr and causing a nonzero exit code :/
/*
  // Generator close hooks: called during GC in this case!!!
  function(d, b) { return "(function () { try { yield " + makeExpr(d, b) + " } finally { " + makeStatement(d, b) + " } })().next()"; },

  function(d, b) { return "(function () { try { yield " + makeExpr(d, b) + " } finally { " + makeStatement(d, b) + " } })()"; },
  function(d, b) { return "(function () { try { yield " + makeExpr(d, b) + " } finally { " + makeStatement(d, b) + " } })"; },
  function(d, b) { 
    return "function gen() { try { yield 1; } finally { " + makeStatement(d, b) + " } } var i = gen(); i.next(); i = null;";
  }

*/
];

function makeTryBlock(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  // Catches: 1/6 chance of having none
  // Catches: maybe 2 + 1/2 
  // So approximately 4 recursions into makeExceptionyStatement on average!
  // Therefore we want to keep the chance of recursing too much down...
  
  d = d - rnd(3);
  

  var s = cat(["try", " { ", makeExceptionyStatement(d, b), " } "]);

  var numCatches = 0;
  
  while(rnd(3) == 0) {
    // Add a guarded catch, using an expression or a function call.
    ++numCatches;
    if (rnd(2))
      s += cat(["catch", "(", makeId(d, b), " if ",                 makeExpr(d, b),                    ")", " { ", makeExceptionyStatement(d, b), " } "]);
    else
      s += cat(["catch", "(", makeId(d, b), " if ", "(function(){", makeExceptionyStatement(d, b), "})())", " { ", makeExceptionyStatement(d, b), " } "]);
  }
  
  if (rnd(2)) {
    // Add an unguarded catch.
    ++numCatches;
    s +=   cat(["catch", "(", makeId(d, b),                                                          ")", " { ", makeExceptionyStatement(d, b), " } "]);
  }
  
  if (numCatches == 0 || rnd(2) == 1) {
    // Add a finally.
    s += cat(["finally", " { ", makeExceptionyStatement(d, b), " } "]);
  }
  
  return s;
}



// Creates a string that sorta makes sense as an expression
function makeExpr(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (d <= 0 || (rnd(7) == 1))
    return makeTerm(d - 1, b);

  if (rnd(6) == 1 && b.length)
    return rndElt(b);

  if (rnd(10) == 1)
    return makeImmediateRecursiveCall(d, b);

  d = rnd(d); // !

  var expr = (rndElt(exprMakers))(d, b);
  
  if (rnd(4) == 1)
    return "(" + expr + ")";
  else
    return expr;
}

var binaryOps = [
  // Long-standing JavaScript operators, roughly in order from http://www.codehouse.com/javascript/precedence/
  " * ", " / ", " % ", " + ", " - ", " << ", " >> ", " >>> ", " < ", " > ", " <= ", " >= ", " instanceof ", " in ", " == ", " != ", " === ", " !== ",
  " & ", " | ", " ^ ", " && ", " || ", " = ", " *= ", " /= ", " %= ", " += ", " -= ", " <<= ", " >>= ", " >>>= ", " &= ", " ^= ", " |= ", " , ",

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
  function(d, b) { return cat([rndElt(leftUnaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([rndElt(leftUnaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([rndElt(leftUnaryOps), makeExpr(d, b)]); },
  
  // Right-unary operators
  function(d, b) { return cat([makeExpr(d, b), rndElt(rightUnaryOps)]); },
  function(d, b) { return cat([makeExpr(d, b), rndElt(rightUnaryOps)]); },
  function(d, b) { return cat([makeExpr(d, b), rndElt(rightUnaryOps)]); },

  // Special properties: we love to set them!
  function(d, b) { return cat([makeExpr(d, b), ".", rndElt(specialProperties)]); },
  function(d, b) { return cat([makeExpr(d, b), ".", rndElt(specialProperties), " = ", makeExpr(d, b)]); },
  function(d, b) { return cat([makeId(d, b),   ".", rndElt(specialProperties), " = ", makeExpr(d, b)]); },
  
  // Methods
  function(d, b) { return cat([makeExpr(d, b), ".", rndElt(objectMethods), "(", makeActualArgList(d, b), ")"]); },
  function(d, b) { return cat([makeExpr(d, b), ".", "valueOf", "(", uneval("number"), ")"]); },

  // Binary operators
  function(d, b) { return cat([makeExpr(d, b), rndElt(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), rndElt(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), rndElt(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), rndElt(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), rndElt(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), rndElt(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), rndElt(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), rndElt(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), rndElt(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), rndElt(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), rndElt(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), rndElt(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), rndElt(binaryOps), makeExpr(d, b)]); },
  
  // Ternary operator
  function(d, b) { return cat([makeExpr(d, b), " ? ", makeExpr(d, b), " : ", makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), " ? ", makeExpr(d, b), " : ", makeExpr(d, b)]); },

  // In most contexts, yield expressions must be parenthesized, so including explicitly parenthesized yields makes actually-compiling yields appear more often.
  function(d, b) { return cat(["yield ", makeExpr(d, b)]); },
  function(d, b) { return cat(["(", "yield ", makeExpr(d, b), ")"]); },
  
  // Array functions (including extras).  The most interesting are map and filter, I think.
  // These are mostly interesting to fuzzers in the sense of "what happens if i do strange things from a filter function?"  e.g. modify the array.. :)
  // This fuzzer isn't the best for attacking this kind of thing, since it's unlikely that the code in the function will attempt to modify the array or make it go away.
  // The second parameter to "map" is used as the "this" for the function.
  function(d, b) { return cat(["[11,12,13,14]",        ".", rndElt(["map", "filter", "some", "sort"]) ]); },
  function(d, b) { return cat(["[15,16,17,18]",        ".", rndElt(["map", "filter", "some", "sort"]), "(", makeFunction(d, b), ", ", makeExpr(d, b), ")"]); },
  function(d, b) { return cat(["[", makeExpr(d, b), "]", ".", rndElt(["map", "filter", "some", "sort"]), "(", makeFunction(d, b), ")"]); },
  
  // RegExp replace.  This is interesting for the same reason as array extras.  Also, in SpiderMonkey, the "this" argument is weird (obj.__parent__?)
  function(d, b) { return cat(["'fafafa'", ".", "replace", "(", "/", "a", "/", "g", ", ", makeFunction(d, b), ")"]); },

  // Dot (property access)
  function(d, b) { return cat([makeId(d, b),    ".", makeId(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b),  ".", makeId(d, b)]); },

  // Index into array
  function(d, b) { return cat([     makeExpr(d, b),      "[", makeExpr(d, b), "]"]); },
  function(d, b) { return cat(["(", makeExpr(d, b), ")", "[", makeExpr(d, b), "]"]); },

  // Containment in an array or object (or, if this happens to end up on the LHS of an assignment, destructuring)
  function(d, b) { return cat([maybeSharpDecl(), "[", makeExpr(d, b), "]"]); },
  function(d, b) { return cat([maybeSharpDecl(), "(", "{", makeId(d, b), ": ", makeExpr(d, b), "}", ")"]); },

  // Sharps on random stuff?
  function(d, b) { return cat([maybeSharpDecl(), makeExpr(d, b)]); },

  // Functions: called immediately/not
  function(d, b) { return makeFunction(d, b); },
  function(d, b) { return cat(["(", makeFunction(d, b), ")", "(", makeActualArgList(d, b), ")"]); },

  // Try to call things that may or may not be functions.
  function(d, b) { return cat([     makeExpr(d, b),          "(", makeActualArgList(d, b), ")"]); },
  function(d, b) { return cat(["(", makeExpr(d, b),     ")", "(", makeActualArgList(d, b), ")"]); },
  function(d, b) { return cat([     makeFunction(d, b),      "(", makeActualArgList(d, b), ")"]); },

  // Try to test function.call heavily.
  function(d, b) { return cat(["(", makeFunction(d, b), ")", ".", "call", "(", makeExpr(d, b), ", ", makeActualArgList(d, b), ")"]); },
  
  // Binary "new", with and without clarifying parentheses, with expressions or functions
  function(d, b) { return cat(["new ",      makeExpr(d, b),          "(", makeActualArgList(d, b), ")"]); },
  function(d, b) { return cat(["new ", "(", makeExpr(d, b), ")",     "(", makeActualArgList(d, b), ")"]); },

  function(d, b) { return cat(["new ",      makeFunction(d, b),      "(", makeActualArgList(d, b), ")"]); },
  function(d, b) { return cat(["new ", "(", makeFunction(d, b), ")", "(", makeActualArgList(d, b), ")"]); },

  // Sometimes we do crazy stuff, like putting a statement where an expression should go.  This frequently causes a syntax error.
  function(d, b) { return stripSemicolon(makeLittleStatement(d, b)); },
  function(d, b) { return ""; },

  // Let expressions -- note the lack of curly braces.
  function(d, b) { var v = makeNewId(d, b); return cat(["let ", "(", v,                            ") ", makeExpr(d - 1, b.concat([v]))]); },
  function(d, b) { var v = makeNewId(d, b); return cat(["let ", "(", v, " = ", makeExpr(d - 1, b), ") ", makeExpr(d - 1, b.concat([v]))]); },
  function(d, b) {                          return cat(["let ", "(", makeLetHead(d, b),            ") ", makeExpr(d, b)]); },

  // Array comprehensions (JavaScript 1.7)
  function(d, b) { return cat(["[", makeExpr(d, b), makeComprehension(d, b), "]"]); },

  // Generator expressions (JavaScript 1.8)
  function(d, b) { return cat([     makeExpr(d, b), makeComprehension(d, b)     ]); },
  function(d, b) { return cat(["(", makeExpr(d, b), makeComprehension(d, b), ")"]); },
  
  // Comments and whitespace
  function(d, b) { return cat([" /* Comment */", makeExpr(d, b)]); },
  function(d, b) { return cat(["\n", makeExpr(d, b)]); }, // perhaps trigger semicolon insertion and stuff
  function(d, b) { return cat([makeExpr(d, b), "\n"]); },

  // LValue as an expression
  function(d, b) { return cat([makeLValue(d, b)]); },

  // Assignment (can be destructuring)
  function(d, b) { return cat([     makeLValue(d, b),      " = ", makeExpr(d, b)     ]); },
  function(d, b) { return cat([     makeLValue(d, b),      " = ", makeExpr(d, b)     ]); },
  function(d, b) { return cat(["(", makeLValue(d, b),      " = ", makeExpr(d, b), ")"]); },
  function(d, b) { return cat(["(", makeLValue(d, b), ")", " = ", makeExpr(d, b)     ]); },

  // Destructuring assignment
  function(d, b) { return cat([     makeDestructuringLValue(d, b),      " = ", makeExpr(d, b)     ]); },
  function(d, b) { return cat([     makeDestructuringLValue(d, b),      " = ", makeExpr(d, b)     ]); },
  function(d, b) { return cat(["(", makeDestructuringLValue(d, b),      " = ", makeExpr(d, b), ")"]); },
  function(d, b) { return cat(["(", makeDestructuringLValue(d, b), ")", " = ", makeExpr(d, b)     ]); },
  
  // Destructuring assignment with lots of group assignment
  function(d, b) { return cat([makeDestructuringLValue(d, b), " = ", makeDestructuringLValue(d, b)]); },
  
  // Modifying assignment, with operators that do various coercions
  function(d, b) { return cat([makeLValue(d, b), rndElt(["|=", "%=", "+=", "-="]), makeExpr(d, b)]); },

  // Watchpoints (similar to setters)
  function(d, b) { return cat([makeExpr(d, b), ".", "watch", "(", uneval(makeId(d, b)), ", ", makeFunction(d, b), ")"]); },
  function(d, b) { return cat([makeExpr(d, b), ".", "unwatch", "(", uneval(makeId(d, b)), ")"]); },
  
  // New-style getter/setter, imperative
  function(d, b) { return cat([makeExpr(d, b), ".", "__defineGetter__", "(", uneval(makeId(d, b)), ", ", makeFunction(d, b), ")"]); },
  function(d, b) { return cat([makeExpr(d, b), ".", "__defineSetter__", "(", uneval(makeId(d, b)), ", ", makeFunction(d, b), ")"]); },
  function(d, b) { return cat(["this", ".", "__defineGetter__", "(", uneval(makeId(d, b)), ", ", makeFunction(d, b), ")"]); },
  function(d, b) { return cat(["this", ".", "__defineSetter__", "(", uneval(makeId(d, b)), ", ", makeFunction(d, b), ")"]); },
  
  // Old-style getter/setter, imperative
  function(d, b) { return cat([makeId(d, b), ".", makeId(d, b), " ", rndElt(["getter", "setter"]), "= ", makeFunction(d, b)]); },

  // Object literal
  function(d, b) { return cat(["(", "{", makeObjLiteralPart(d, b), " }", ")"]); },
  function(d, b) { return cat(["(", "{", makeObjLiteralPart(d, b), ", ", makeObjLiteralPart(d, b), " }", ")"]); },
  
  // Test js_ReportIsNotFunction heavily.
  function(d, b) { return "(p={}, (p.z = " + makeExpr(d, b) + ")())"; },

  // Test js_ReportIsNotFunction heavily.
  // Test decompilation for ".keyword" a bit.
  // Test throwing-into-generator sometimes.
  function(d, b) { return cat([makeExpr(d, b), ".", "throw", "(", makeExpr(d, b), ")"]); },
  function(d, b) { return cat([makeExpr(d, b), ".", "yoyo",   "(", makeExpr(d, b), ")"]); },

  // Throws, but more importantly, tests js_DecompileValueGenerator in various contexts.
  function(d, b) { return "this.zzz.zzz"; }, 
  
  // Test eval in various contexts. (but avoid clobbering eval)
  // Test the special "obj.eval" and "eval(..., obj)" forms.
  function(d, b) { return makeExpr(d, b) + ".eval(" + makeExpr(d, b) + ")"; },
  function(d, b) { return "eval(" + uneval(makeExpr(d, b)) + ")"; },
  function(d, b) { return "eval(" + uneval(makeExpr(d, b)) + ", " + makeExpr(d, b) + ")"; },
  function(d, b) { return "eval(" + uneval(makeStatement(d, b)) + ")"; },
  function(d, b) { return "eval(" + uneval(makeStatement(d, b)) + ", " + makeExpr(d, b) + ")"; },
  
  // Uneval needs more testing than it will get accidentally.  No cat() because I don't want uneval clobbered (assigned to) accidentally.
  function(d, b) { return "(uneval(" + makeExpr(d, b) + "))"; },
  
  // Constructors.  No cat() because I don't want to screw with the constructors themselves, just call them.
  function(d, b) { return "new " + rndElt(constructors) + "(" + makeActualArgList(d, b) + ")"; },
  function(d, b) { return          rndElt(constructors) + "(" + makeActualArgList(d, b) + ")"; },

  // Turn on gczeal in the middle of something
  function(d, b) { return "gczeal(" + makeZealLevel() + ")"; },

  // Unary Math functions
  function (d, b) { return "Math." + rndElt(["abs", "acos", "asin", "atan", "ceil", "cos", "exp", "floor", "log", "round", "sin", "sqrt", "tan"]) + "(" + makeExpr(d, b) + ")"; },

  // Binary Math functions
  function (d, b) { return "Math." + rndElt(["atan2", "max", "min", "pow"]) + "(" + makeExpr(d, b) + ", " + makeExpr(d, b) + ")"; }
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
    function(d, b) { return cat([makeId(d, b),  ".", "(", makeExpr(d, b), ")"]); },
    function(d, b) { return cat([makeE4X(d, b),  ".", "(", makeExpr(d, b), ")"]); },
  ]);
}


var constructors = [
  "Error", "RangeError", "Exception",
  "Function", "RegExp", "String", "Array", "Object", "Number", "Boolean", 
  // "Date",  // commented out due to appearing "random, but XXX want to use it sometimes...
  "Iterator"
];

function maybeSharpDecl()
{
  if (rnd(3) == 0)
    return cat(["#", "" + (rnd(3)), "="]);
  else
    return "";
}


function makeObjLiteralPart(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  switch(rnd(8))
  {
    // Old-style literal getter/setter
    case 0: return cat([makeId(d, b), " getter: ", makeFunction(d, b)]);
    case 1: return cat([makeId(d, b), " setter: ", makeFunction(d, b)]);
    
    // New-style literal getter/setter
    case 2: return cat([" get ", makeId(d, b), maybeName(d, b), "(", makeFormalArgList(d - 1, b), ")", makeFunctionBody(d, b)]);
    case 3: return cat([" set ", makeId(d, b), maybeName(d, b), "(", makeFormalArgList(d - 1, b), ")", makeFunctionBody(d, b)]);
    


/*
    case 3: return cat(["toString: ", makeFunction(d, b), "}", ")"]);
    case 4: return cat(["toString: function() { return this; } }", ")"]); }, // bwahaha
    case 5: return cat(["toString: function() { return " + makeExpr(d, b) + "; } }", ")"]); },
    case 6: return cat(["valueOf: ", makeFunction(d, b), "}", ")"]); },
    case 7: return cat(["valueOf: function() { return " + makeExpr(d, b) + "; } }", ")"]); },
*/

    default: return cat([makeId(d, b), ": ", makeExpr(d, b)]);
  }
}




function makeFunction(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  d = d - 1;
  
  if(rnd(5) == 1)
    return makeExpr(d, b);

  return (rndElt(functionMakers))(d, b);
}


function makeFunPrefix(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  switch(rnd(20)) {
// Leaving this stuff out until bug 381203 is fixed.
// Eventually this stuff should be moved from functionMakers to somewhere
// like statementMakers, right?
//    case 0: return "getter ";
//    case 1: return "setter ";
    default: return "";
  }
}

function maybeName(d, b)
{
  if (rnd(2) == 0)
    return " " + makeId(d, b) + " ";
  else
    return "";
}

function makeFunctionBody(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  switch(rnd(4)) {
    case 0:  return cat([" { ", makeStatement(d - 1, b),   " } "]);
    case 1:  return cat([" { ", "return ", makeExpr(d, b), " } "]);
    case 2:  return cat([" { ", "yield ",  makeExpr(d, b), " } "]);
    default: return makeExpr(d, b); // make an "expression closure"
  }
}



var functionMakers = [
  // Note that a function with a name is sometimes considered a statement rather than an expression.

  // Functions and expression closures
  function(d, b) { var v = makeNewId(d, b); return cat([makeFunPrefix(d, b), "function", " ", maybeName(d, b), "(", v,                       ")", makeFunctionBody(d, b.concat([v]))]); },
  function(d, b) {                          return cat([makeFunPrefix(d, b), "function", " ", maybeName(d, b), "(", makeFormalArgList(d, b), ")", makeFunctionBody(d, b)]); },
  
  // Methods
  function(d, b) { return cat([makeExpr(d, b), ".", rndElt(objectMethods)]); }, 

  // The identity function
  function(d, b) { return "function(q) { return q; }" },

  // A generator that does something
  function(d, b) { return "function(y) { yield y; " + makeStatement(d, b.concat(["y"])) + "; yield y; }" }, 
  
  // A generator expression -- kinda a function??
  function(d, b) { return "(1 for (x in []))"; },
  
  // Special functions that might have interesting results, especially when called "directly" by things like string.replace or array.map.
  function(d, b) { return "eval" }, // eval is interesting both for its "no indirect calls" feature and for the way it's implemented -- a special bytecode.
  function(d, b) { return "new Function" }, // this won't be interpreted the same way for each caller of makeFunction, but that's ok
  function(d, b) { return "(new Function(" + uneval(makeStatement(d, b)) + "))"; },
  function(d, b) { return "Function" }, // without "new"!  it does seem to work...
  function(d, b) { return "gc" },
  function(d, b) { return "Math.sin" },
  function(d, b) { return "Math.pow" },
  function(d, b) { return "/a/gi" }, // in Firefox, at least, regular expressions can be used as functions: e.g. "hahaa".replace(/a+/g, /aa/g) is "hnullhaa"!
];
  



/*
David Anderson suggested creating the following recursive structures:
  - recurse down an array of mixed types, car cdr kinda thing
  - multiple recursive calls in a function, like binary search left/right, sometimes calls neither and sometimes calls both

  the recursion support in spidermonkey only works with self-recursion.
  that is, two functions that call each other recursively will not be traced.

  two trees are formed, going down and going up.
  type instability matters on both sides.
  so the values returned from the function calls matter.

  so far, what i've thought of means recursing from the top of a function and if..else.
  but i'd probably also want to recurse from other points, e.g. loops.

  special code for tail recursion likely coming soon, but possibly as a separate patch, because it requires changes to the interpreter.
*/

// "@" indicates a point at which a statement can be inserted. XXX allow use of variables, as consts
// variable names will be replaced, and should be uppercase to reduce the chance of matching things they shouldn't.
// take care to ensure infinite recursion never occurs unexpectedly, especially with doubly-recursive functions.
var recursiveFunctions = [
  {
    text: "(function too_much_recursion(depth) { @; if (depth > 0) { @; too_much_recursion(depth - 1); } @ })",
    vars: ["depth"],
    args: function(d, b) { return rnd(10000); },
    test: function(f) { try { f(5000); } catch(e) { } return true; }
  },
  {
    text: "(function factorial(N) { @; if (N == 0) return 1; @; return N * factorial(N - 1); @ })",
    vars: ["N"],
    args: function(d, b) { return "" + rnd(20); },
    test: function(f) { return f(10) == 3628800; }
  },
  {
    text: "(function factorial_tail(N, Acc) { @; if (N == 0) { @; return Acc; } @; return factorial_tail(N - 1, Acc * N); @ })",
    vars: ["N", "Acc"],
    args: function(d, b) { return rnd(20) + ", 1"; },
    test: function(f) { return f(10, 1) == 3628800; }
  },
  {
    // two recursive calls
    text: "(function fibonacci(N) { @; if (N <= 1) { @; return 1; } @; return fibonacci(N - 1) + fibonacci(N - 2); @ })",
    vars: ["N"],
    args: function(d, b) { return "" + rnd(8); },
    test: function(f) { return f(6) == 13; }
  },
  {
    // this lets us play a little with mixed-type arrays
    text: "(function sum_indexing(array, start) { @; return array.length == start ? 0 : array[start] + sum_indexing(array, start + 1); })",
    vars: ["array", "start"],
    args: function(d, b) { return makeMixedTypeArray(d-1, b) + ", 0"; },
    test: function(f) { return f([1,2,3,"4",5,6,7], 0) == "123418"; }
  },
  {
    text: "(function sum_slicing(array) { @; return array.length == 0 ? 0 : array[0] + sum_slicing(array.slice(1)); })",
    vars: ["array"],
    args: function(d, b) { return makeMixedTypeArray(d-1, b); },
    test: function(f) { return f([1,2,3,"4",5,6,7]) == "123418"; }
  }
];

(function testAllRecursiveFunctions() {
  for (var i = 0; i < recursiveFunctions.length; ++i) {
    var a = recursiveFunctions[i];
    var f = eval(a.text.replace(/@/g, ""))
    if (!a.test(f))
      throw "Failed test of: " + a.text;
  }
})();

function makeImmediateRecursiveCall(d, b)
{
  var a = rndElt(recursiveFunctions);
  var s = a.text;
  for (var i = 0; i < a.vars.length; ++i)
    s = s.replace(new RegExp(a.vars[i], "g"), uniqueVarName());
  s = s + "(" + a.args(d, b) + ")";
  s = s.replace(/@/g, function() { if (rnd(4) == 0) return makeExpr(d-2, b); return ""; });
  s = "(" + s + ")";
  return s;
}

function makeLetHead(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (rnd(2) == 1)
    return makeLetHeadItem(d, b);
  else
    return makeLetHeadItem(d, b) + ", " + makeLetHeadItem(d - 1, b);
}

function makeLetHeadItem(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  d = d - 1;
  
  // 0 or more things being declared
  var lhs = (rnd(3) == 1) ? makeDestructuringLValue(d, b) : makeId(d, b);
  
  // initial value
  var rhs = (rnd(2) == 1) ? (" = " + makeExpr(d, b)) : "";
  
  return lhs + rhs;
}


function makeActualArgList(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  var nArgs = rnd(3);

  if (nArgs == 0)
    return "";

  var argList = makeExpr(d, b);

  for (var i = 1; i < nArgs; ++i)
    argList += ", " + makeExpr(d - i, b);

  return argList;
}

function makeFormalArgList(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  var nArgs = rnd(3);

  if (nArgs == 0)
    return "";

  var argList = makeFormalArg(d, b)

  for (var i = 1; i < nArgs; ++i)
    argList += ", " + makeFormalArg(d - i, b);
    
  return argList;
}

function makeFormalArg(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (rnd(4) == 1)
    return makeDestructuringLValue(d, b);
  
  return makeId(d, b);
}


function makeNewId(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);
  
  return rndElt(["a", "b", "c", "d", "e", "w", "x", "y", "z"]);
}

function makeId(d, b) 
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);
  
  if (rnd(2) == 1 && b.length)
    return rndElt(b);

  switch(rnd(200))
  {
  case 0:
    return makeTerm(d, b);
  case 1:  
    return makeExpr(d, b);
  case 2: case 3: case 4: case 5:  
    return makeLValue(d, b);
  case 6: case 7:
    return makeDestructuringLValue(d, b);
  case 8: case 9: case 10:
    // some keywords that can be used as identifiers in some contexts (e.g. variables, function names, argument names)
    // but that's annoying, and some of these cause lots of syntax errors.
    return rndElt(["get", "set", "getter", "setter", "delete", "let", "yield", "each"]);
  case 11:
    return "function::" + makeId(d, b);
  case 12: case 13:
    return "this." + makeId(d, b);
  case 14:
    return "x::" + makeId(d, b);
  case 15: case 16:
    return rndElt(specialProperties);
  }

  return rndElt(["a", "b", "c", "d", "e", "w", "x", "y", "z",
                 "window", "this", "eval", "\u3056", "NaN",
//                 "valueOf", "toString", // e.g. valueOf getter :P // bug 381242, etc
                 "functional", // perhaps decompiler code looks for "function"?
                 " " // [k, v] becomes [, v] -- test how holes are handled in unexpected destructuring
                  ]);

  // window is a const (in the browser), so some attempts to redeclare it will cause errors

  // eval is interesting because it cannot be called indirectly. and maybe also because it has its own opcode in jsopcode.tbl.
  // but bad things happen if you have "eval setter"... so let's not put eval in this list.
}


function makeComprehension(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (d < 0)
    return "";

  switch(rnd(5)) {
  case 0:
    return "";
  case 1:
    return cat([" for ",          "(", makeForInLHS(d, b), " in ", makeExpr(d - 2, b),           ")"]) + makeComprehension(d - 1, b);
  case 2:
    return cat([" for ", "each ", "(", makeId(d, b),       " in ", makeExpr(d - 2, b),           ")"]) + makeComprehension(d - 1, b);
  case 3:
    return cat([" for ", "each ", "(", makeId(d, b),       " in ", makeMixedTypeArray(d - 2, b), ")"]) + makeComprehension(d - 1, b);
  default:
    return cat([" if ", "(", makeExpr(d - 2, b), ")"]); // this is always last (and must be preceded by a "for", oh well)
  }
}




// for..in LHS can be a single variable OR it can be a destructuring array of exactly two elements.
function makeForInLHS(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

// JS 1.7 only (removed in JS 1.8)
//
//  if (version() == 170 && rnd(4) == 0)
//    return cat(["[", makeLValue(d, b), ", ", makeLValue(d, b), "]"]);

  return makeLValue(d, b);
}


function makeLValue(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (d <= 0 || (rnd(2) == 1))
    return makeId(d - 1, b);

  d = rnd(d);

  return (rndElt(lvalueMakers))(d, b);
}


var lvalueMakers = [
  // Simple variable names :)
  function(d, b) { return cat([makeId(d, b)]); },

  // Destructuring
  function(d, b) { return makeDestructuringLValue(d, b); },
  function(d, b) { return "(" + makeDestructuringLValue(d, b) + ")"; },
  
  // Properties
  function(d, b) { return cat([makeId(d, b), ".", makeId(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), ".", makeId(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), "[", "'", makeId(d, b), "'", "]"]); },

  // Special properties
  function(d, b) { return cat([makeId(d, b), ".", rndElt(specialProperties)]); },

  // Certain functions can act as lvalues!  See JS_HAS_LVALUE_RETURN in js engine source.
  function(d, b) { return cat([makeId(d, b), "(", makeExpr(d, b), ")"]); },
  function(d, b) { return cat(["(", makeExpr(d, b), ")", "(", makeExpr(d, b), ")"]); },

  // Parenthesized lvalues can cause problems ;)
  function(d, b) { return cat(["(", makeLValue(d, b), ")"]); },

  function(d, b) { return makeExpr(d, b); } // intentionally bogus, but not quite garbage.
];

function makeDestructuringLValue(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  d = d - 1;

  if (d < 0 || rnd(4) == 1)
    return makeId(d, b);

  if (rnd(6) == 1)
    return makeLValue(d, b);

  return (rndElt(destructuringLValueMakers))(d, b);
}

var destructuringLValueMakers = [
  // destructuring assignment: arrays
  function(d, b) 
  { 
    var len = rnd(d, b);
    if (len == 0)
      return "[]";
      
    var Ti = [];
    Ti.push("[");
    Ti.push(maybeMakeDestructuringLValue(d, b));
    for (var i = 1; i < len; ++i) {
      Ti.push(", ");
      Ti.push(maybeMakeDestructuringLValue(d, b));    
    }
    
    Ti.push("]");
    
    return cat(Ti);    
  },

  // destructuring assignment: objects
  function(d, b)
  {
    var len = rnd(d, b);
    if (len == 0)
      return "{}";
    var Ti = [];
    Ti.push("{");
    for (var i = 0; i < len; ++i) {
      if (i > 0)
        Ti.push(", ");
      Ti.push(makeId(d, b));
      if (rnd(3)) {
        Ti.push(": ");
        Ti.push(makeDestructuringLValue(d, b));
      } // else, this is a shorthand destructuring, treated as "id: id".
    }
    Ti.push("}");
    
    return cat(Ti);
  }
];

// Allow "holes".
function maybeMakeDestructuringLValue(d, b)
{
  if (rnd(2) == 0)
    return ""
    
  return makeDestructuringLValue(d, b)
}



function makeTerm(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  return (rndElt(termMakers))(d, b);
}

var termMakers = [
  // Variable names
  function(d, b) { return makeId(d, b); },

  // Simple literals (no recursion required to make them)
  function(d, b) { return rndElt([ 
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
  function(d, b) { return rndElt([ "0.1", ".2", "3", "1.3", "4.", "5.0000000000000000000000", "1.2e3", "1e81", "1e+81", "1e-81", "1e4", "0", "-0", "(-0)", "-1", "(-1)", "0x99", "033", (""+Math.PI), "3/0", "-3/0", "0/0"
    // these are commented out due to bug 379294
    // "0x2D413CCC", "0x5a827999", "0xB504F332", "(0x50505050 >> 1)"
  ]); },
  function(d, b) { return rndElt([ "true", "false", "undefined", "null"]); },
  function(d, b) { return rndElt([ "this", "window" ]); },
  function(d, b) { return rndElt([" \"\" ", " '' ", " /x/ ", " /x/g "]) },
];

if (haveE4X) {
  // E4X literals
  termMakers = termMakers.concat([
  function(d, b) { return rndElt([ "<x/>", "<y><z/></y>"]); },
  function(d, b) { return rndElt([ "@foo" /* makes sense in filtering predicates, at least... */, "*", "*::*"]); },
  function(d, b) { return makeE4X(d, b) }, // xml
  function(d, b) { return cat(["<", ">", makeE4X(d, b), "<", "/", ">"]); }, // xml list
  ]);
}


function maybeMakeTerm(d, b)
{
  if (rnd(2))
    return makeTerm(d - 1, b);
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


function makeE4X(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (d <= 0)
    return cat(["<", "x", ">", "<", "y", "/", ">", "<", "/", "x", ">"]);
    
  d = d - 1;
  
  var y = [
    function(d, b) { return '<employee id="1"><name>Joe</name><age>20</age></employee>' },
    function(d, b) { return cat(["<", ">", makeSubE4X(d, b), "<", "/", ">"]); }, // xml list

    function(d, b) { return cat(["<", ">", makeExpr(d, b), "<", "/", ">"]); }, // bogus or text
    function(d, b) { return cat(["<", "zzz", ">", makeExpr(d, b), "<", "/", "zzz", ">"]); }, // bogus or text
    
    // mimic parts of this example at a time, from the e4x spec: <x><{tagname} {attributename}={attributevalue+attributevalue}>{content}</{tagname}></x>;

    function(d, b) { var tagId = makeId(d, b); return cat(["<", "{", tagId, "}", ">", makeSubE4X(d, b), "<", "/", "{", tagId, "}", ">"]); },
    function(d, b) { var attrId = makeId(d, b); var attrValExpr = makeExpr(d, b); return cat(["<", "yyy", " ", "{", attrId, "}", "=", "{", attrValExpr, "}", " ", "/", ">"]); },
    function(d, b) { var contentId = makeId(d, b); return cat(["<", "yyy", ">", "{", contentId, "}", "<", "/", "yyy", ">"]); },
    
    // namespace stuff
    function(d, b) { var contentId = makeId(d, b); return cat(['<', 'bbb', ' ', 'xmlns', '=', '"', makeExpr(d, b), '"', '>', makeSubE4X(d, b), '<', '/', 'bbb', '>']); },
    function(d, b) { var contentId = makeId(d, b); return cat(['<', 'bbb', ' ', 'xmlns', ':', 'ccc', '=', '"', makeExpr(d, b), '"', '>', '<', 'ccc', ':', 'eee', '>', '<', '/', 'ccc', ':', 'eee', '>', '<', '/', 'bbb', '>']); },
    
    function(d, b) { return makeExpr(d, b); },
    
    function(d, b) { return makeSubE4X(d, b); }, // naked cdata things, etc.
  ]
  
  return (rndElt(y))(d, b);
}

function makeSubE4X(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

// Bug 380431
//  if (rnd(8) == 0)
//    return "<" + "!" + "[" + "CDATA[" + makeExpr(depth - 1) + "]" + "]" + ">"

  if (d < -2)
    return "";

  var y = [
    function(d, b) { return cat(["<", "ccc", ":", "ddd", ">", makeSubE4X(d - 1, b), "<", "/", "ccc", ":", "ddd", ">"]); },
    function(d, b) { return makeE4X(d, b) + makeSubE4X(d - 1, b); },
    function(d, b) { return "yyy"; },
    function(d, b) { return cat(["<", "!", "--", "yy", "--", ">"]); }, // XML comment
// Bug 380431
//    function(depth) { return cat(["<", "!", "[", "CDATA", "[", "zz", "]", "]", ">"]); }, // XML cdata section
    function(d, b) { return " "; },
    function(d, b) { return ""; },
  ];
  
  return (rndElt(y))(d, b);
}

function makeMixedTypeArray(d, b)
{
  
  var a = [
    // Numbers and number-like things
    [
    "0", "1", "2", "3", "0.1", ".2", "1.3", "4.", "5.0000000000000000000000", 
    "1.2e3", "1e81", "1e+81", "1e-81", "1e4", "-0", "(-0)",
    "-1", "(-1)", "0x99", "033", "3/0", "-3/0", "0/0", 
    "Math.PI",
    "0x2D413CCC", "0x5a827999", "0xB504F332", "-0x2D413CCC", "-0x5a827999", "-0xB504F332", "0x50505050", "(0x50505050 >> 1)",
    // various powers of two, with values near JSVAL_INT_MAX especially tested
    "0x10000000", "0x20000000", "0x3FFFFFFE", "0x3FFFFFFF", "0x40000000", "0x40000001", "0x80000000", "-0x80000000", 
    ],
  
    // Special numbers
    [ "(1/0)", "(-1/0)", "(0/0)" ],
  
    // Strings and regular expressions
    [" \"\" ", " '' ", " 'A' ", " '\\0' "],
    
    // Regular expressions (can have "side effects" due to bug 98409)
    [ " /x/ ", " /x/g "],
   
    // Booleans
    [ "true", "false" ],
    
    // Undefined and null
    [ "(void 0)", "null" ],
    
    // Object literals
    [ "[]", "[1]", "[(void 0)]", "{}", "{x:3}", "({})", "({x:3})" ],
  
    // Variables that really should have been constants in the ecmascript spec
    [ "NaN", "Infinity", "-Infinity", "undefined"],
    
    // Boxed booleans
    [ "new Boolean(true)", "new Boolean(false)" ],
    
    // Boxed numbers
    [ "new Number(1)", "new Number(1.5)" ],
    
    // Boxed strings
    [ "new String('')", "new String('q')" ],
  
    // Fun stuff
    [ "function(){}", "{}", "[]", "[1]", "['z']", "[undefined]", "this", "eval", "arguments" ],
  
    // Actual variables (slightly dangerous)
    [ rndElt(b), rndElt(b) ]
  ];
  
  // Pick two to five of those
  var q = rnd(4) + 2;
  var picks = [];
  for (var j = 0; j < q; ++j)
    picks.push(rndElt(rndElt(a)));

  // Make an array of up to 39 elements, containing those two to five values
  var c = [];
  var count = rnd(40);
  for (var j = 0; j < count; ++j)
    c.push(rndElt(picks));

  return "[" + c.join(", ") + "]";
}





var count = 0;
var verbose = false;


var maxHeapCount = 0;
var sandbox = null;
//var nextTrapCode = null;
// https://bugzilla.mozilla.org/show_bug.cgi?id=394853#c19
//try { eval("/") } catch(e) { }
// Remember the number of countHeap.
tryItOut("");




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
// SPLICE DDBEGIN
start();
// SPLICE DDEND

if (jsshell)
  print("It's looking good!"); // Magic string that jsunhappy.py looks for


// 3. Run it.

// In this file:
// * Chunking of steps for speed
// * Recording and playing, to make reduction possible
// * Things to aid automated reduction with Lithium (DD* markers, fuzzPriv.quitApplication)
// * Pausing (Esc pauses, Shift+Esc unpauses)

var fuzzIsStrictMode = (function() { return !this; })();

var dumpEachCommand = false; // Can be set to true by using the "Record as it goes" reduction strategy and setting it to record.  Also, some fuzzers always set this to true.
var dumpEachSeed = false; // Can be set to true if makeCommand has side effects, such as crashing, so you have to reduce "the hard way".
var pleaseSerializeDOMAsScript = false; // Can be set to true (and often is) ...
var gPageCompleted = false;
var reportAllErrors = false;
var fuzzExpectSanity = (location.href.indexOf("xslt") == -1 && location.href.indexOf("xml-stylesheet") == -1);

var fuzzCount;

var oPrefix  = "  /*FRCA1*/ "; // most recording output, including all random commands
var oPrefix2 = "  /*FRCA2*/ "; // dom reconstruction


function fuzzOnload(ev)
{
  // Work around bug 380537.
  if (Random.twister) {
    dumpln("fuzzOnload called twice!?");
    return;
  }

  if (window != top) {
    dumpln("I'm in some kind of frame!?");
    return;
  }

  if (window.opener) {
    dumpln("I have an opener!?");
    return;
  }

  if (history.length > 1 && "fuzzPriv" in window) {
    // This check is for some of the crazier stuff fuzzerDuringEvents does.
    // Unfortunately, it breaks the "&scan" tests that are nice for testing outside of the Firefox harness.
    // And it also breaks fuzzRetry.
    dumpln("I have history!?");
    fuzzPriv.quitApplicationSoon();
    return;
  }

  initFuzzerGeneral();

  // initFuzzerSpecific() is expected to call startFuzzing.  Most fuzzers call it immediately but some use a timeout or callback.

  if (rnd(2)) {
    // Go now! (On DOMContentLoaded)
    initFuzzerSpecific();
  } else {
    // Let the page do its onload things first.
    window.addEventListener("load", function() { setTimeout(initFuzzerSpecific, 50); }, false);
  }
}

function initFuzzerGeneral()
{
  // Prevent bad things from happening when svg:script nodes are cloned,
  // and keep some confusion out of addDOMNodes (perhaps)
  for (var i = 1; i <= 6; ++i) {
    try {
      rM(document.getElementById("fuzz" + i));
    } catch(e) {
      // dumpln("Nothing to remove?");
    }
  }

  obtainSettings();

  dumpln("FRCX Fuzzer: " + fuzzerName);
  dumpln("FRCX URL: " + location.href);
  dumpln("FRCX Content type: " + document.contentType);
  if (document.doctype)
    dumpln("FRCX Doctype: <!DOCTYPE " + document.doctype.name + (document.doctype.publicId ? " PUBLIC \"" + document.doctype.publicId + "\"" + (document.doctype.systemId ? " \"" + document.doctype.systemId + "\"" : "") : "") + ">");

  Random.init(fuzzSeed);
}


function startFuzzing(kickoff)
{
  if (window.fuzzCommands) {
    // Already recorded, so we should play.
    fuzzCount = 0;
    playFunsChunk();
  }
  else {
    // Not already recorded
    if (recordStrategy == "Record as it goes") {
      dumpEachCommand = true;
    }

    if (recordMode) {
      recordSomehow();
    } else {
      dumpln(oPrefix + "var fuzzSettings = [" + fuzzSettings + "];");
      dumpln(oPrefix + "var fuzzCommands = [];");

      kickoff();

      immedChunk(numImmediate || stepsPerInterval);
    }
  }
}

function recordSomehow()
{
  switch(recordStrategy) {
    case "Record without doing":
      if (maxSteps == Infinity)
        alert("You must specify maxSteps to record with this fuzzer.");
      else
        recordFuns();

      break;

    case "Record as it goes":
      // alert("This fuzzer records as it goes.  If you encounter a crash or other bug you want to reduce, grep console output for lines containing origCount and paste that in as a fuzzCommands array.");
      immedChunk(numImmediate || stepsPerInterval);
      break;

    default:
      alert("This fuzzer doesn't seem to support recording.");
  }
}


var immedCount = 0;

function immedChunk(changes)
{
  if (!gPageCompleted && !pauseFuzzing) {
    if (immedCount > maxSteps) {
      gPageCompleted = true; // Tell Spider we're done.
      pauseFuzzing = true; // Don't keep printing useless stuff every 100 steps, don't keep trying to load the next page in the scan.
    }
    else {

      for (var i = 0; i < changes; ++i) {
        ++immedCount;
        if (!pauseFuzzing && immedCount <= maxSteps)
          immedStep();
      }

      if (dumpEachCommand) {
        dumpln(fuzzRecord(oPrefix, immedCount, "rest: true"));
      }

    }
  }

  // gPageCompleted may have been set before immedChunk() was called, or
  // as a result of immedStep(), or by code *in* immedChunk!?
  if (gPageCompleted) {
    if (getURLParam("scan")) {
      // Take advantage of seed being the first parameter to replace it easily.
      location.search = location.search.replace("fuzz=" + fuzzSeed, "fuzz=" + (fuzzSeed + 1));
    }
  }
  else if (stepsPerInterval !== 0)
    setTimeout(function() { immedChunk(stepsPerInterval); }, interval);
}


function fuzzTryMakeCommand()
{
  var MTA = Random.twister.export_mta();
  var MTI = Random.twister.export_mti();

  function dumpRNGStateBefore()
  {
    // Captured upvars: MTA, MTI
    var MTA_str = uneval(MTA);
    // More complicated, but results in a much shorter script, making SpiderMonkey happier.
    if (MTA_str != rnd.lastDumpedMTA) {
      dumpln(fuzzRecord(oPrefix, immedCount, "fun: function() { if (Random.twister) { Random.twister.import_mta(" + MTA_str + "); } }"));
      rnd.lastDumpedMTA = MTA_str;
    }
    dumpln(fuzzRecord(oPrefix, immedCount, "fun: function() { if (Random.twister) { Random.twister.import_mti(" + MTI + "); void (fuzzTryMakeCommand()); } }"));
  }

  if (dumpEachSeed) {
    dumpRNGStateBefore();
  }

  // Call makeCommand, checking that it doesn't throw.
  var commandStrings;
  try {
    commandStrings = makeCommand();
  } catch(e) {
    try {
      if (!dumpEachSeed) {
        dumpRNGStateBefore();
      }
      if (fuzzExpectSanity) {
        dumpln("FAILURE: makeCommand threw an exception");
      }
      dumpln("STOPPING (" + e + ")");
      dumpln(e.stack);
    } catch(e2) {
      dumpln("STOPPING, ???");
    }
    fuzzPriv.quitApplicationSoon();
    throw "Stopping!";
  }

  if (typeof commandStrings == "string")
    commandStrings = [commandStrings];

  var f;
  var commands = [];

  // Check that all the commands compile.
  for (var i = 0; i < commandStrings.length; ++i) {
    var s = commandStrings[i];
    if (s.length > 4000000) {
      // e.g. backslash-escaping a string over and over
      dumpln("String from makeCommand is too long.");
      continue;
    }
    try {
      // The 'void 3' is here to catch missing-semicolon bugs in the fuzzer.
      f = new Function(s + " void 3");
    } catch(e) {
      if (!dumpEachSeed) {
        dumpRNGStateBefore();
      }
      if (fuzzExpectSanity) {
        dumpln("FAILURE: Can't compile: " + s);
      }
      dumpln("Can't compile: " + simpleSource(s));
      dumpln(e);
      continue;
    }
    if (dumpEachCommand) {
      dumpln(fuzzRecord(oPrefix, immedCount, "fun: function() { " + s + " }"));
    }
    commands.push({str: s, fun: f});
  }

  return commands;
}

function immedStep()
{
  if (!dumpEachCommand && immedCount % (100) === 0) {
    // Dump stuff occasionally so that if we hit a crash, we have a hint as to where we hit it.
    dumpln(fuzzerName + ": " + immedCount);
  }

  var commands = fuzzTryMakeCommand();
  for (var i = 0; i < commands.length; ++i) {
    fuzzTryCommand(commands[i].fun, immedCount + "." + i);
  }
}

var fuzzMirrors = [];

function fuzzTryCommand(fun, note)
{
  function fail()
  {
    // In addition to uncatchable exceptions, this can happen because of:
    // * Something prevented clearTimeout from working (e.g. window.__proto__ = otherWindow)
    // * XHR (freezes scripts in some windows but not all)
    // * window.open (spins the event loop)
    // So, no "FAILURE:".
    dumpln("Uncatchable exception from " + note + "!?");
    fuzzPriv.quitApplicationSoon();
    fuzzExpectSanity = false;
  }

  var failtimer = setTimeout(fail, 0);

  for (var i = 0; i < fuzzMirrors.length; ++i) {
    try {
      fuzzMirrors[i](fun, note);
    } catch(e) {
    }
  }

  try {
    fun();
  } catch(e) {
    var errorAsString = "";

    try {
      errorAsString = "" + e;
    } catch(e2) {
      errorAsString = "[cannot convert this exception to string!]";
    }

    if (reportAllErrors)
      dumpln("Thrown from " + note + ": " + errorAsString);
  }

  clearTimeout(failtimer);
}


/************
 * SETTINGS *
 ************/

var fuzzSeed = 0;
var numImmediate = 0;
var stepsPerInterval = 100;
var interval = 150;
var maxSteps = Infinity;
var recordMode = 0;


function obtainSettings()
{

  // if (window.fuzzSettings === undefined) alert("No settings variable declaration? No fuzzer?");
  // Let's just allow this to hit an error, instead of putting up an annoying alert whenever a fuzzer has a typo or we're reducing like crazy but keeping fuzzPriv.quitApplication.

  if (fuzzSettings == null)
    fuzzSettings = getURLParam("fuzz");

  if (fuzzSettings == null)
    fuzzSettings = prompt(fuzzerName + " settings\n\nSeed\nNumber of changes in first chunk\nNumber of changes in each subsequent chunk\nInterval between chunks in milliseconds\nTotal number of changes (or 0 for unlimited)\n1 to record, 0 to go", "0, 0, 100, 150, 0, 0");

  if (fuzzSettings == null) {
    fuzzSeed = 0; // for playing around with javascript: URLs, accessing o[...], etc.
    numImmediate = stepsPerInterval = maxSteps = 0;
    interval = 1000;
    // throw "User hit cancel!";
    return;
  }

  if (typeof fuzzSettings == "string") {
    fuzzSettings = fuzzSettings.replace(/;/g, ","); // allow semicolons in place of commas (makes Talkback's URL field happier)
    fuzzSettings = eval("[" + fuzzSettings + "]");
  }

  if (fuzzSettings[0]) fuzzSeed         = fuzzSettings[0];
  if (fuzzSettings[1]) numImmediate     = fuzzSettings[1];
  if (fuzzSettings[2]) stepsPerInterval = fuzzSettings[2];
  if (fuzzSettings[3]) interval         = fuzzSettings[3];
  if (fuzzSettings[4]) maxSteps         = fuzzSettings[4]; // if it's 0, it remains Infinity!
  if (fuzzSettings[5]) recordMode       = fuzzSettings[5];
}

function getURLParam(p)
{
  var s = location.search + "&";
  var r = new RegExp("[?&]" + p + "\\=([^&]*)\\&");
  if(r.exec(s) == null)
    return null;
  var raw = RegExp.$1;
  return unescape(raw.replace(/\+/g," "));
}


/***********
 * PAUSING *
 ***********/

var pauseFuzzing = false;

function escPause(ev)
{
  if (ev.keyCode == 27) { // esc
    if (!ev.shiftKey) {
      dumpln("Pausing fuzzing.");
      pauseFuzzing = true;
    } else {
      // Shift+Esc (works in Firefox but not in Safari)
      dumpln("Resuming fuzzing.");
      pauseFuzzing = false;
    }
  }
}

// IE compat
if (!window.addEventListener) {
  window.addEventListener      = function(ev, func, _) { return window.attachEvent  ('on' + ev, func); };
  document.addEventListener    = function(ev, func, _) { return document.attachEvent('on' + ev, func); };
}
if (!window.removeEventListener) {
  window.removeEventListener   = function(ev, func, _) { return window.detachEvent  ('on' + ev, func); };
  document.addEventListener    = function(ev, func, _) { return document.attachEvent('on' + ev, func); };
}

// Commented out because fuzzerFakeEvents
// window.addEventListener("keypress", escPause, false);




/*********************************
 * SIMPLE RECORDING AND PLAYBACK *
 *********************************/

function playFuns()
{
  var command = fuzzCommands[fuzzCount];

  ++fuzzCount;

  if (command == null)
    return false;

  if (command.origCount != null)
    dumpln("origCount: " + command.origCount);

  if (command.fun) {
    fuzzTryCommand(command.fun, "origCount==" + command.origCount);
  }

  return command;
}


function playFunsChunk()
{
  var playFunsRet = playFuns();

  while(playFunsRet && !playFunsRet.rest)
    playFunsRet = playFuns();

  // Use custom interval if specified, otherwise use default interval
  var timeout = (playFunsRet && "timeout" in playFunsRet) ? playFunsRet.timeout : interval;

  setTimeout(playFunsChunk, timeout);
}


// recordFuns is only used with recordStrategy == "Record without doing".
// (This strategy is kinda obsolete.)
// Otherwise, immedStep does the recording (optionally).
function recordFuns()
{
  // This is nice in that it avoids verbose output...
  var fuzzCommands = [];

  var output =
     oPrefix + "var fuzzSettings = [" + fuzzSettings + "];\n" +
     oPrefix + "var fuzzCommands = [];\n" +
     oPrefix + "// DD" + "BEGIN\n";

  for (var fuzzCount = 1; fuzzCount <= maxSteps; ++fuzzCount)
  {
    var commands = fuzzTryMakeCommand();

    for (var i = 0; i < commands.length; ++i)
      output += fuzzRecord(oPrefix, fuzzCount + "fun: function() { " + commands[i].str + " }") + "\n";

    var countAfterImmed = fuzzCount - numImmediate;
    if((countAfterImmed >= 0) && (countAfterImmed % stepsPerInterval === 0)) {
      output += fuzzRecord(oPrefix, fuzzCount, "rest: true") + "\n";
    }
  }

  output += oPrefix + "// DD" + "END\n";

  dumpln("// Paste this into the script, replacing the first two lines:\n\n" + output);
}

function fuzzRecord(prefix, count, x)
{
  function lineUp(s)
  {
    s = "" + s;
    while (s.length < 5)
      s = " " + s;
    return s;
  }
  return prefix + "fuzzCommands.push({ origCount: " + lineUp(count) + ", " + x.replace(/<\/script/g, "<\\/script") + " });";
}


/**********
 * OUTPUT *
 **********/

function dumpln(s)
{
  if (self.dump) // Firefox debug
    dump((""+s).replace(/\0/g, "\\0") + "\n"); // bug 359433
  else if (self.console) // Safari 2
    console.log((""+s).replace(/%/g, "%%"));
}


/*********************
 * REDUCTION HELPERS *
 *********************/

function fuzzRetry(maxTimes)
{
  return function() {
    var s = getURLParam("retry");
    var n = (s != null) ? parseInt(s, 10) : 0;

    if (maxTimes && (n >= maxTimes)) {
      dumpln("fuzzRetry: done");
      fuzzPriv.quitApplication();
    } else {
      location.search = "?retry=" + (n + 1);
    }
  };
}

function fuzzReset(maxTimes)
{
  return function() {
    ++fuzzResetCount;
    dumpln("fuzzResetCount == " + fuzzResetCount);

    if (maxTimes && (fuzzResetCount >= maxTimes)) {
      dumpln("fuzzReset: done");
      fuzzPriv.quitApplication();
    }
    else {
      fuzzCount = 0;
    }
  };
}

var fuzzResetCount = 0;

// Cheap test to check e.g.
// * Is the final DOM is enough to trigger the bug?
// * Is the penultimate DOM, along with the final statement, enough to trigger the bug?
// If so, perhaps you'll want to serialize up to that point (as HTML or XHTML or a script).
function fuzzBounceDE()
{
  var de = document.documentElement;
  document.removeChild(de);
  document.appendChild(de);
}


window.addEventListener("DOMContentLoaded", function() { dumpln(">> DOMContentLoaded"); }, false);
window.addEventListener("load", function() { dumpln(">> load"); }, false);

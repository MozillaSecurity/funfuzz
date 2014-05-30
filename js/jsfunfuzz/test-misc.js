
function optionalTests(f, code, wtt)
{
  if (count % 100 == 1) {
    tryHalves(code);
  }

  if (count % 100 == 2 && engine == ENGINE_SPIDERMONKEY_TRUNK) {
    try {
      Reflect.parse(code);
    } catch(e) {
    }
  }

  if (0 && engine == ENGINE_SPIDERMONKEY_TRUNK) {
    if (wtt.allowExec && (typeof sandbox == "function")) {
      f = null;
      if (trySandboxEval(code, false)) {
        dumpln("Trying it again to see if it's a 'real leak' (???)");
        trySandboxEval(code, true);
      }
    }
  }

  if (count % 100 == 3 && f && typeof disassemble == "function") {
    // It's hard to use the recursive disassembly in the comparator,
    // but let's at least make sure the disassembler itself doesn't crash.
    disassemble("-r", f);
  }

  if (0 && f && wtt.allowExec && engine == ENGINE_SPIDERMONKEY_TRUNK) {
    simpleDVGTest(code);
    tryEnsureSanity();
  }

  if (count % 100 == 6 && f && wtt.allowExec && wtt.expectConsistentOutput && wtt.expectConsistentOutputAcrossIter
    && engine == ENGINE_SPIDERMONKEY_TRUNK && getBuildConfiguration()['more-deterministic']) {
    nestingConsistencyTest(code);
  }
}


function simpleDVGTest(code)
{
  var fullCode = "(function() { try { \n" + code + "\n; throw 1; } catch(exx) { this.nnn.nnn } })()";

  try {
    eval(fullCode);
  } catch(e) {
    if (e.message != "this.nnn is undefined" && e.message.indexOf("redeclaration of") == -1) {
      foundABug("Wrong error message", e);
    }
  }
}

var maxHeapCount = 0;
var sandbox = null;

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
    var currentHeapCount = countHeap();
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
    void ("" + f);
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
    void ("" + f);
  }
  catch(e) {
    if (verbose)
      dumpln("Second half compilation error: " + e);
  }
}


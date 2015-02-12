
/****************************
 * GRAMMAR-BASED GENERATION *
 ****************************/


function makeScript(d, ignoredB)
{
  return directivePrologue() + makeScriptBody(d, ignoredB);
}

function makeScriptBody(d, ignoredB)
{
  if (rnd(3) == 0) {
    return makeMathyFunAndTest(d, ["x"]);
  }
  return makeStatement(d, ["x"]);
}

function makeScriptForEval(d, b)
{
  switch (rnd(4)) {
    case 0:  return makeExpr(d - 1, b);
    case 1:  return makeStatement(d - 1, b);
    case 2:  return makeUseRegressionTest(d, b);
    default: return makeScript(d - 3, b);
  }
}


// Statement or block of statements
function makeStatement(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (rnd(2))
    return makeBuilderStatement(d, b);

  if (d < 6 && rnd(3) === 0)
    return makePrintStatement(d, b);

  if (d < rnd(8)) // frequently for small depth, infrequently for large depth
    return makeLittleStatement(d, b);

  d = rnd(d); // !

  return (Random.index(statementMakers))(d, b);
}

var varBinder = ["var ", "let ", "const ", ""];
var varBinderFor = ["var ", "let ", ""]; // const is a syntax error in for loops

// The reason there are several types of loops here is to create different
// types of scripts without introducing infinite loops.

function forLoopHead(d, b, v, reps)
{
  var sInit = Random.index(varBinderFor) + v + " = 0";
  var sCond = v + " < " + reps;
  var sNext = "++" + v;

  while (rnd(10) === 0)
    sInit += ", " + makeLetHeadItem(d - 2, b);
  while (rnd(10) === 0)
    sInit += ", " + makeExpr(d - 2, b); // NB: only makes sense if our varBinder is ""

  while (rnd(20) === 0)
    sCond = sCond + " && (" + makeExpr(d - 2, b) + ")";
  while (rnd(20) === 0)
    sCond = "(" + makeExpr(d - 2, b) + ") && " + sCond;

  while (rnd(20) === 0)
    sNext = sNext + ", " + makeExpr(d - 2, b);
  while (rnd(20) === 0)
    sNext = makeExpr(d - 2, b) + ", " + sNext;

  return "for (" + sInit + "; " + sCond + "; " + sNext + ")";
}

function makeOpaqueIdiomaticLoop(d, b)
{
  var reps = loopCount();
  var vHidden = uniqueVarName();
  return "/*oLoop*/" + forLoopHead(d, b, vHidden, reps) + " { " +
      makeStatement(d - 2, b) +
      " } ";
}

function makeTransparentIdiomaticLoop(d, b)
{
  var reps = loopCount();
  var vHidden = uniqueVarName();
  var vVisible = makeNewId(d, b);
  return "/*vLoop*/" + forLoopHead(d, b, vHidden, reps) +
    " { " +
      Random.index(varBinder) + vVisible + " = " + vHidden + "; " +
      makeStatement(d - 2, b.concat([vVisible])) +
    " } ";
}

function makeBranchUnstableLoop(d, b)
{
  var reps = loopCount();
  var v = uniqueVarName();
  var mod = loopModulo();
  var target = rnd(mod);
  return "/*bLoop*/" + forLoopHead(d, b, v, reps) + " { " +
    "if (" + v + " % " + mod + " == " + target + ") { " + makeStatement(d - 2, b) + " } " +
    "else { " + makeStatement(d - 2, b) + " } " +
    " } ";
}

function makeTypeUnstableLoop(d, b) {
  var a = makeMixedTypeArray(d, b);
  var v = makeNewId(d, b);
  var bv = b.concat([v]);
  return "/*tLoop*/for each (let " + v + " in " + a + ") { " + makeStatement(d - 2, bv) + " }";
}


function makeFunOnCallChain(d, b) {
  var s = "arguments.callee";
  while (rnd(2))
    s += ".caller";
  return s;
}


var statementMakers = Random.weighted([

  // Any two statements in sequence
  { w: 15, v: function(d, b) { return cat([makeStatement(d - 1, b),       makeStatement(d - 1, b)      ]); } },
  { w: 15, v: function(d, b) { return cat([makeStatement(d - 1, b), "\n", makeStatement(d - 1, b), "\n"]); } },

  // Stripping semilcolons.  What happens if semicolons are missing?  Especially with line breaks used in place of semicolons (semicolon insertion).
  { w: 1, v: function(d, b) { return cat([stripSemicolon(makeStatement(d, b)), "\n", makeStatement(d, b)]); } },
  { w: 1, v: function(d, b) { return cat([stripSemicolon(makeStatement(d, b)), "\n"                   ]); } },
  { w: 1, v: function(d, b) { return stripSemicolon(makeStatement(d, b)); } }, // usually invalid, but can be ok e.g. at the end of a block with curly braces

  // Simple variable declarations, followed (or preceded) by statements using those variables
  { w: 4, v: function(d, b) { var v = makeNewId(d, b); return cat([Random.index(varBinder), v, " = ", makeExpr(d, b), ";", makeStatement(d - 1, b.concat([v]))]); } },
  { w: 4, v: function(d, b) { var v = makeNewId(d, b); return cat([makeStatement(d - 1, b.concat([v])), Random.index(varBinder), v, " = ", makeExpr(d, b), ";"]); } },

  // Complex variable declarations, e.g. "const [a,b] = [3,4];" or "var a,b,c,d=4,e;"
  { w: 10, v: function(d, b) { return cat([Random.index(varBinder), makeLetHead(d, b), ";", makeStatement(d - 1, b)]); } },

  // Blocks
  { w: 2, v: function(d, b) { return cat(["{", makeStatement(d, b), " }"]); } },
  { w: 2, v: function(d, b) { return cat(["{", makeStatement(d - 1, b), makeStatement(d - 1, b), " }"]); } },

  // "with" blocks
  { w: 2, v: function(d, b) {                          return cat([maybeLabel(), "with", "(", makeExpr(d, b), ")",                    makeStatementOrBlock(d, b)]);             } },
  { w: 2, v: function(d, b) { var v = makeNewId(d, b); return cat([maybeLabel(), "with", "(", "{", v, ": ", makeExpr(d, b), "}", ")", makeStatementOrBlock(d, b.concat([v]))]); } },

  // C-style "for" loops
  // Two kinds of "for" loops: one with an expression as the first part, one with a var or let binding 'statement' as the first part.
  // I'm not sure if arbitrary statements are allowed there; I think not.
  { w: 1, v: function(d, b) {                          return "/*infloop*/" + cat([maybeLabel(), "for", "(", makeExpr(d, b), "; ", makeExpr(d, b), "; ", makeExpr(d, b), ") ", makeStatementOrBlock(d, b)]); } },
  { w: 1, v: function(d, b) { var v = makeNewId(d, b); return "/*infloop*/" + cat([maybeLabel(), "for", "(", Random.index(varBinderFor), v,                                                    "; ", makeExpr(d, b), "; ", makeExpr(d, b), ") ", makeStatementOrBlock(d, b.concat([v]))]); } },
  { w: 1, v: function(d, b) { var v = makeNewId(d, b); return "/*infloop*/" + cat([maybeLabel(), "for", "(", Random.index(varBinderFor), v, " = ", makeExpr(d, b),                             "; ", makeExpr(d, b), "; ", makeExpr(d, b), ") ", makeStatementOrBlock(d, b.concat([v]))]); } },
  { w: 1, v: function(d, b) {                          return "/*infloop*/" + cat([maybeLabel(), "for", "(", Random.index(varBinderFor), makeDestructuringLValue(d, b), " = ", makeExpr(d, b), "; ", makeExpr(d, b), "; ", makeExpr(d, b), ") ", makeStatementOrBlock(d, b)]); } },

  // Various types of "for" loops, specially set up to test tracing, carefully avoiding infinite loops
  { w: 6, v: makeTransparentIdiomaticLoop },
  { w: 6, v: makeOpaqueIdiomaticLoop },
  { w: 6, v: makeBranchUnstableLoop },
  { w: 8, v: makeTypeUnstableLoop },

  // "for..in" loops
  // arbitrary-LHS marked as infloop because
  // -- for (key in obj)
  { w: 1, v: function(d, b) {                          return "/*infloop*/" + cat([maybeLabel(), "for", "(", Random.index(varBinderFor), makeForInLHS(d, b), " in ", makeExpr(d - 2, b), ") ", makeStatementOrBlock(d, b)]); } },
  { w: 1, v: function(d, b) { var v = makeNewId(d, b); return                 cat([maybeLabel(), "for", "(", Random.index(varBinderFor), v,                  " in ", makeExpr(d - 2, b), ") ", makeStatementOrBlock(d, b.concat([v]))]); } },
  // -- for (key in generator())
  { w: 1, v: function(d, b) {                          return "/*infloop*/" + cat([maybeLabel(), "for", "(", Random.index(varBinderFor), makeForInLHS(d, b), " in ", "(", "(", makeFunction(d, b), ")", "(", makeExpr(d, b), ")", ")", ")", makeStatementOrBlock(d, b)]); } },
  { w: 1, v: function(d, b) { var v = makeNewId(d, b); return                 cat([maybeLabel(), "for", "(", Random.index(varBinderFor), v,                  " in ", "(", "(", makeFunction(d, b), ")", "(", makeExpr(d, b), ")", ")", ")", makeStatementOrBlock(d, b.concat([v]))]); } },
  // -- for each (value in obj)
  { w: 1, v: function(d, b) {                          return "/*infloop*/" + cat([maybeLabel(), " for ", " each", "(", Random.index(varBinderFor), makeLValue(d, b), " in ", makeExpr(d - 2, b), ") ", makeStatementOrBlock(d, b)]); } },
  { w: 1, v: function(d, b) { var v = makeNewId(d, b); return                 cat([maybeLabel(), " for ", " each", "(", Random.index(varBinderFor), v,                " in ", makeExpr(d - 2, b), ") ", makeStatementOrBlock(d, b.concat([v]))]); } },

  // Modify something during a loop -- perhaps the thing being looped over
  // Since we use "let" to bind the for-variables, and only do wacky stuff once, I *think* this is unlikely to hang.
//  function(d, b) { return "let forCount = 0; for (let " + makeId(d, b) + " in " + makeExpr(d, b) + ") { if (forCount++ == " + rnd(3) + ") { " + makeStatement(d - 1, b) + " } }"; },

  // Hoisty "for..in" loops.  I don't know why this construct exists, but it does, and it hoists the initial-value expression above the loop.
  // With "var" or "const", the entire thing is hoisted.
  // With "let", only the value is hoisted, and it can be elim'ed as a useless statement.
  // The last form is specific to JavaScript 1.7 (only).
  { w: 1, v: function(d, b) {                                               return cat([maybeLabel(), "for", "(", Random.index(varBinderFor), makeId(d, b),         " = ", makeExpr(d, b), " in ", makeExpr(d - 2, b), ") ", makeStatementOrBlock(d, b)]); } },
  { w: 1, v: function(d, b) { var v = makeNewId(d, b);                      return cat([maybeLabel(), "for", "(", Random.index(varBinderFor), v,                    " = ", makeExpr(d, b), " in ", makeExpr(d - 2, b), ") ", makeStatementOrBlock(d, b.concat([v]))]); } },
  { w: 1, v: function(d, b) { var v = makeNewId(d, b), w = makeNewId(d, b); return cat([maybeLabel(), "for", "(", Random.index(varBinderFor), "[", v, ", ", w, "]", " = ", makeExpr(d, b), " in ", makeExpr(d - 2, b), ") ", makeStatementOrBlock(d, b.concat([v, w]))]); } },

  // do..while
  { w: 1, v: function(d, b) { return cat([maybeLabel(), "while((", makeExpr(d, b), ") && 0)" /*don't split this, it's needed to avoid marking as infloop*/, makeStatementOrBlock(d, b)]); } },
  { w: 1, v: function(d, b) { return "/*infloop*/" + cat([maybeLabel(), "while", "(", makeExpr(d, b), ")", makeStatementOrBlock(d, b)]); } },
  { w: 1, v: function(d, b) { return cat([maybeLabel(), "do ", makeStatementOrBlock(d, b), " while((", makeExpr(d, b), ") && 0)" /*don't split this, it's needed to avoid marking as infloop*/, ";"]); } },
  { w: 1, v: function(d, b) { return "/*infloop*/" + cat([maybeLabel(), "do ", makeStatementOrBlock(d, b), " while", "(", makeExpr(d, b), ");"]); } },

  // Switch statement
  { w: 3, v: function(d, b) { return cat([maybeLabel(), "switch", "(", makeExpr(d, b), ")", " { ", makeSwitchBody(d, b), " }"]); } },

  // "let" blocks, with bound variable used inside the block
  { w: 2, v: function(d, b) { var v = makeNewId(d, b); return cat(["let ", "(", v, ")", " { ", makeStatement(d, b.concat([v])), " }"]); } },

  // "let" blocks, with and without multiple bindings, with and without initial values
  { w: 2, v: function(d, b) { return cat(["let ", "(", makeLetHead(d, b), ")", " { ", makeStatement(d, b), " }"]); } },

  // Conditionals, perhaps with 'else if' / 'else'
  { w: 1, v: function(d, b) { return cat([maybeLabel(), "if(", makeBoolean(d, b), ") ", makeStatementOrBlock(d, b)]); } },
  { w: 1, v: function(d, b) { return cat([maybeLabel(), "if(", makeBoolean(d, b), ") ", makeStatementOrBlock(d - 1, b), " else ", makeStatementOrBlock(d - 1, b)]); } },
  { w: 1, v: function(d, b) { return cat([maybeLabel(), "if(", makeBoolean(d, b), ") ", makeStatementOrBlock(d - 1, b), " else ", " if ", "(", makeExpr(d, b), ") ", makeStatementOrBlock(d - 1, b)]); } },
  { w: 1, v: function(d, b) { return cat([maybeLabel(), "if(", makeBoolean(d, b), ") ", makeStatementOrBlock(d - 1, b), " else ", " if ", "(", makeExpr(d, b), ") ", makeStatementOrBlock(d - 1, b), " else ", makeStatementOrBlock(d - 1, b)]); } },

  // A tricky pair of if/else cases.
  // In the SECOND case, braces must be preserved to keep the final "else" associated with the first "if".
  { w: 1, v: function(d, b) { return cat([maybeLabel(), "if(", makeBoolean(d, b), ") ", "{", " if ", "(", makeExpr(d, b), ") ", makeStatementOrBlock(d - 1, b), " else ", makeStatementOrBlock(d - 1, b), "}"]); } },
  { w: 1, v: function(d, b) { return cat([maybeLabel(), "if(", makeBoolean(d, b), ") ", "{", " if ", "(", makeExpr(d, b), ") ", makeStatementOrBlock(d - 1, b), "}", " else ", makeStatementOrBlock(d - 1, b)]); } },

  // Expression statements
  { w: 5, v: function(d, b) { return cat([makeExpr(d, b), ";"]); } },
  { w: 5, v: function(d, b) { return cat(["(", makeExpr(d, b), ")", ";"]); } },

  // Exception-related statements :)
  { w: 6, v: function(d, b) { return makeExceptionyStatement(d - 1, b) + makeExceptionyStatement(d - 1, b); } },
  { w: 7, v: function(d, b) { return makeExceptionyStatement(d, b); } },

  // Labels. (JavaScript does not have goto, but it does have break-to-label and continue-to-label).
  { w: 1, v: function(d, b) { return cat(["L", ": ", makeStatementOrBlock(d, b)]); } },

  // Function-declaration-statements with shared names
  { w: 10, v: function(d, b) { return cat([makeStatement(d-2, b), "function ", makeId(d, b), "(", makeFormalArgList(d, b), ")", makeFunctionBody(d - 1, b), makeStatement(d-2, b)]); } },

  // Function-declaration-statements with unique names, along with calls to those functions
  { w: 8, v: makeNamedFunctionAndUse },

  // Long script -- can confuse Spidermonkey's short vs long jmp or something like that.
  // Spidermonkey's regexp engine is so slow for long strings that we have to bypass whatToTest :(
  //{ w: 1, v: function(d, b) { return strTimes("try{}catch(e){}", rnd(10000)); } },
  { w: 1, v: function(d, b) { if (rnd(200)==0) return "/*DUPTRY" + rnd(10000) + "*/" + makeStatement(d - 1, b); return ";"; } },

  { w: 1, v: function(d, b) { return makeShapeyConstructorLoop(d, b); } },

  // Replace a variable with a long linked list pointing to it.  (Forces SpiderMonkey's GC marker into a stackless mode.)
  { w: 1, v: function(d, b) { var x = makeId(d, b); return x + " = linkedList(" + x + ", " + (rnd(100) * rnd(100)) + ");";  } },

  // Oddly placed "use strict" or "use asm"
  { w: 1, v: function(d, b) { return directivePrologue() + makeStatement(d - 1, b); } },

  // Spidermonkey GC and JIT controls
  { w: 3, v: function(d, b) { return makeTestingFunctionCall(d, b); } },
  { w: 3, v: function(d, b) { return makeTestingFunctionCall(d - 1, b) + " " + makeStatement(d - 1, b); } },

  // Blocks of statements related to typed arrays
  { w: 8, v: makeTypedArrayStatements },

  // Print statements
  { w: 8, v: makePrintStatement },

  { w: 20, v: makeRegexUseBlock },

  { w: 1, v: makeRegisterStompBody },

  { w: 20, v: makeUseRegressionTest },

  // Discover properties to add to the allPropertyNames list
  //{ w: 3, v: function(d, b) { return "for (var p in " + makeId(d, b) + ") { addPropertyName(p); }"; } },
  //{ w: 3, v: function(d, b) { return "var opn = Object.getOwnPropertyNames(" + makeId(d, b) + "); for (var j = 0; j < opn.length; ++j) { addPropertyName(opn[j]); }"; } },
]);


function makeUseRegressionTest(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (typeof regressionTestList != "object") {
    return "/* no regression tests found */";
  }

  var maintest = Random.index(regressionTestList);
  var files = regressionTestDependencies(maintest);

  var s = "";

  if (rnd(5) == 0) {
    // Many tests call assertEq, intending to throw if something unexpected happens.
    // Sometimes, override it with a function that compares but does not throw.
    s += "assertEq = function(x, y) { if (x != y) { print(0); } }; ";
  }

  for (var i = 0; i < files.length; ++i) {
    var file = files[i];
    if (read(file).indexOf("SIMD") != -1) {
      // Disable SIMD testing until it's more stable (and we can get better stacks?)
      continue;
    }

    switch (rnd(2)) {
      case 0:
        // simply inline the script -- this is the only one that will work in newGlobal()
        s += "/* regression-test-inline */ " + inlineRegressionTest(file);
        break;
      default:
        // run it using load()
        s += "/* regression-test-load */ " + "load(" + simpleSource(file) + ");";
        break;
      // NB: these scripts will also be run through eval(), evalcx(), evaluate() thanks to other parts of the fuzzer using makeScriptForEval or makeStatement
    }
  }
  return s;
}

function inlineRegressionTest(filename)
{
  // Inline a regression test, adding NODIFF (to disable differential testing) if it calls a testing function that might throw.

  const s = "/* " + filename + " */ " + read(filename) + "\n";

  const noDiffTestingFunctions = [
    // These can throw
    "gcparam",
    "startgc",
    "setJitCompilerOption",
    "disableSingleStepProfiling",
    "enableSingleStepProfiling",
    // These return values depending on command-line options, and some regression tests check them
    "isAsmJSCompilationAvailable",
    "isSimdAvailable", // in 32-bit x86 builds, it depends on whether --no-fpu is passed in, because --no-fpu also disables SSE
    "countHeap",
    "PerfMeasurement",
  ];

  for (var f of noDiffTestingFunctions) {
    if (s.indexOf(f) != -1) {
      return "/*NODIFF*/ " + s;
    }
  }

  return s;
}


function regressionTestDependencies(maintest)
{
  var files = [];

  if (rnd(3)) {
    // Include the chain of 'shell.js' files in their containing directories (starting from regressionTestsRoot)
    for (var i = regressionTestsRoot.length; i < maintest.length; ++i) {
      if (maintest.charAt(i) == "/" || maintest.charAt(i) == "\\") {
        var shelljs = maintest.substr(0, i + 1) + "shell.js";
        if (regressionTestList.indexOf(shelljs) != -1) {
          files.push(shelljs);
        }
      }
    }

    // Include prolog.js for jit-tests
    if (maintest.indexOf("jit-test") != -1) {
      files.push(libdir + "prolog.js");
    }
  }

  files.push(maintest);
  return files;
}


function linkedList(x, n)
{
  for (var i = 0; i < n; ++i)
    x = {a: x};
  return x;
}

function makeNamedFunctionAndUse(d, b) {
  // Use a unique function name to make it less likely that we'll accidentally make a recursive call
  var funcName = uniqueVarName();
  var formalArgList = makeFormalArgList(d, b);
  var bv = formalArgList.length == 1 ? b.concat(formalArgList) : b;
  var declStatement = cat(["/*hhh*/function ", funcName, "(", formalArgList, ")", "{", makeStatement(d - 1, bv), "}"]);
  var useStatement;
  if (rnd(2)) {
    // Direct call
    useStatement = cat([funcName, "(", makeActualArgList(d, b), ")", ";"]);
  } else {
    // Any statement, allowed to use the name of the function
    useStatement = "/*iii*/" + makeStatement(d - 1, b.concat([funcName]));
  }
  if (rnd(2)) {
    return declStatement + useStatement;
  } else {
    return useStatement + declStatement;
  }
}

function makePrintStatement(d, b)
{
  if (rnd(2) && b.length)
    return "print(" + Random.index(b) + ");";
  else
    return "print(" + makeExpr(d, b) + ");";
}


function maybeLabel()
{
  if (rnd(4) === 1)
    return cat([Random.index(["L", "M"]), ":"]);
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
        // cases with numbers (integers?) have special optimizations,
        // so be sure to test those well in addition to testing complicated expressions.
        output += "case " + (rnd(2) ? rnd(10) : makeExpr(d, b)) + ": ";
      }

      haveSomething = true;
    }

    // Might want a statement.
    if (rnd(2))
      output += makeStatement(d, b);

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

  if (rnd(4) === 1)
    return makeStatement(d, b);

  return (Random.index(littleStatementMakers))(d, b);
}

var littleStatementMakers =
[
  // Tiny
  function(d, b) { return cat([";"]); }, // e.g. empty "if" block
  function(d, b) { return cat(["{", "}"]); }, // e.g. empty "if" block
  function(d, b) { return cat([""]); },

  // Throw stuff.
  function(d, b) { return cat(["throw ", makeExpr(d, b), ";"]); },

  // Break/continue [to label].
  function(d, b) { return cat([Random.index(["continue", "break"]), " ", Random.index(["L", "M", "", ""]), ";"]); },

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
];


// makeStatementOrBlock exists because often, things have different behaviors depending on where there are braces.
// for example, if braces are added or removed, the meaning of "let" can change.
function makeStatementOrBlock(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  return (Random.index(statementBlockMakers))(d - 1, b);
}

var statementBlockMakers = [
  function(d, b) { return makeStatement(d, b); },
  function(d, b) { return makeStatement(d, b); },
  function(d, b) { return cat(["{", makeStatement(d, b), " }"]); },
  function(d, b) { return cat(["{", makeStatement(d - 1, b), makeStatement(d - 1, b), " }"]); },
];


// Extra-hard testing for try/catch/finally and related things.

function makeExceptionyStatement(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  d = d - 1;
  if (d < 1)
    return makeLittleStatement(d, b);

  return (Random.index(exceptionyStatementMakers))(d, b);
}

var exceptionProperties = ["constructor", "message", "name", "fileName", "lineNumber", "stack"];

var exceptionyStatementMakers = [
  function(d, b) { return makeTryBlock(d, b); },

  function(d, b) { return makeStatement(d, b); },
  function(d, b) { return makeLittleStatement(d, b); },

  function(d, b) { return "return;"; }, // return without a value can be mixed with yield
  function(d, b) { return cat(["return ", makeExpr(d, b), ";"]); },
  function(d, b) { return cat(["yield ", makeExpr(d, b), ";"]); },
  function(d, b) { return cat(["throw ", makeId(d, b), ";"]); },
  function(d, b) { return "throw StopIteration;"; },
  function(d, b) { return "this.zzz.zzz;"; }, // throws; also tests js_DecompileValueGenerator in various locations
  function(d, b) { return b[b.length - 1] + "." + Random.index(exceptionProperties) + ";"; },
  function(d, b) { return makeId(d, b) + "." + Random.index(exceptionProperties) + ";"; },
  function(d, b) { return cat([makeId(d, b), " = ", makeId(d, b), ";"]); },
  function(d, b) { return cat([makeLValue(d, b), " = ", makeId(d, b), ";"]); },

  // Iteration uses StopIteration internally.
  // Iteration is also useful to test because it asserts that there is no pending exception.
  function(d, b) { var v = makeNewId(d, b); return "for(let " + v + " in []);"; },
  function(d, b) { var v = makeNewId(d, b); return "for(let " + v + " in " + makeIterable(d, b) + ") " + makeExceptionyStatement(d, b.concat([v])); },
  function(d, b) { var v = makeNewId(d, b); return "for(let " + v + " of " + makeIterable(d, b) + ") " + makeExceptionyStatement(d, b.concat([v])); },

  // Brendan says these are scary places to throw: with, let block, lambda called immediately in let expr.
  // And I think he was right.
  function(d, b) { return "with({}) "   + makeExceptionyStatement(d, b);         },
  function(d, b) { return "with({}) { " + makeExceptionyStatement(d, b) + " } "; },
  function(d, b) { var v = makeNewId(d, b); return "let(" + v + ") { " + makeExceptionyStatement(d, b.concat([v])) + "}"; },
  function(d, b) { var v = makeNewId(d, b); return "let(" + v + ") ((function(){" + makeExceptionyStatement(d, b.concat([v])) + "})());"; },
  function(d, b) { return "let(" + makeLetHead(d, b) + ") { " + makeExceptionyStatement(d, b) + "}"; },
  function(d, b) { return "let(" + makeLetHead(d, b) + ") ((function(){" + makeExceptionyStatement(d, b) + "})());"; },

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
  // Therefore we want to keep the chance of recursing too much down.

  d = d - rnd(3);


  var s = cat(["try", " { ", makeExceptionyStatement(d, b), " } "]);

  var numCatches = 0;

  while(rnd(3) === 0) {
    // Add a guarded catch, using an expression or a function call.
    ++numCatches;
    var catchId = makeId(d, b);
    var catchBlock = makeExceptionyStatement(d, b.concat([catchId]));
    if (rnd(2))
      s += cat(["catch", "(", catchId, " if ",                 makeExpr(d, b),                    ")", " { ", catchBlock, " } "]);
    else
      s += cat(["catch", "(", catchId, " if ", "(function(){", makeExceptionyStatement(d, b), "})())", " { ", catchBlock, " } "]);
  }

  if (rnd(2)) {
    // Add an unguarded catch.
    ++numCatches;
    var catchId = makeId(d, b);
    var catchBlock = makeExceptionyStatement(d, b.concat([catchId]));
    s +=   cat(["catch", "(", catchId,                                                          ")", " { ", catchBlock, " } "]);
  }

  if (numCatches == 0 || rnd(2) === 1) {
    // Add a finally.
    s += cat(["finally", " { ", makeExceptionyStatement(d, b), " } "]);
  }

  return s;
}



// Creates a string that sorta makes sense as an expression
function makeExpr(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (d <= 0 || (rnd(7) === 1))
    return makeTerm(d - 1, b);

  if (rnd(6) === 1 && b.length)
    return Random.index(b);

  if (rnd(10) === 1)
    return makeImmediateRecursiveCall(d, b);

  d = rnd(d); // !

  var expr = (Random.index(exprMakers))(d, b);

  if (rnd(4) === 1)
    return "(" + expr + ")";
  else
    return expr;
}

var binaryOps = [
  // Long-standing JavaScript operators, roughly in order from http://www.codehouse.com/javascript/precedence/
  " * ", " / ", " % ", " + ", " - ", " << ", " >> ", " >>> ", " < ", " > ", " <= ", " >= ", " instanceof ", " in ", " == ", " != ", " === ", " !== ",
  " & ", " | ", " ^ ", " && ", " || ", " = ", " *= ", " /= ", " %= ", " += ", " -= ", " <<= ", " >>= ", " >>>= ", " &= ", " ^= ", " |= ", " , ",
];

var leftUnaryOps = [
  "!", "+", "-", "~",
  "void ", "typeof ", "delete ",
  "new ", // but note that "new" can also be a very strange left-binary operator
  "yield " // see http://www.python.org/dev/peps/pep-0342/ .  Often needs to be parenthesized, so there's also a special exprMaker for it.
];

var incDecOps = [
  "++", "--",
];


var specialProperties = [
  "__iterator__", "__count__",
  "__noSuchMethod__",
  "__parent__", "__proto__", "constructor", "prototype",
  "wrappedJSObject",
  "arguments", "caller", "callee",
  "toString", "toSource", "valueOf",
  "call", "apply", // ({apply:...}).apply() hits a special case (speculation failure with funapply / funcall bytecode)
  "length",
  "0", "1",
];

// This makes it easier for fuzz-generated code to mess with the fuzzer. Will I regret it?
/*
function addPropertyName(p)
{
  p = "" + p;
  if (
      p != "floor" &&
      p != "random" &&
      p != "parent" && // unsafe spidermonkey shell function, see bug 619064
      true) {
    print("Adding: " + p);
    allPropertyNames.push(p);
  }
}
*/

var exprMakers =
[
  // Increment and decrement
  function(d, b) { return cat([makeLValue(d, b), Random.index(incDecOps)]); },
  function(d, b) { return cat([Random.index(incDecOps), makeLValue(d, b)]); },

  // Other left-unary operators
  function(d, b) { return cat([Random.index(leftUnaryOps), makeExpr(d, b)]); },

  // Methods
  function(d, b) { var id = makeId(d, b); return cat(["/*UUV1*/", "(", id, ".", Random.index(allMethodNames), " = ", makeFunction(d, b), ")"]); },
  function(d, b) { var id = makeId(d, b); return cat(["/*UUV2*/", "(", id, ".", Random.index(allMethodNames), " = ", id, ".", Random.index(allMethodNames), ")"]); },
  function(d, b) { return cat([makeExpr(d, b), ".", Random.index(allMethodNames), "(", makeActualArgList(d, b), ")"]); },
  function(d, b) { return cat([makeExpr(d, b), ".", "valueOf", "(", uneval("number"), ")"]); },

  // Binary operators
  function(d, b) { return cat([makeExpr(d, b), Random.index(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), Random.index(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), Random.index(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), Random.index(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), Random.index(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), Random.index(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), Random.index(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), Random.index(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), Random.index(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b), Random.index(binaryOps), makeExpr(d, b)]); },
  function(d, b) { return cat([makeId(d, b),   Random.index(binaryOps), makeId(d, b)]); },
  function(d, b) { return cat([makeId(d, b),   Random.index(binaryOps), makeId(d, b)]); },
  function(d, b) { return cat([makeId(d, b),   Random.index(binaryOps), makeId(d, b)]); },

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
  function(d, b) { return cat([makeArrayLiteral(d, b), ".", Random.index(["map", "filter", "some", "sort"]) ]); },
  function(d, b) { return cat([makeArrayLiteral(d, b), ".", Random.index(["map", "filter", "some", "sort"]), "(", makeFunction(d, b), ", ", makeExpr(d, b), ")"]); },
  function(d, b) { return cat([makeArrayLiteral(d, b), ".", Random.index(["map", "filter", "some", "sort"]), "(", makeFunction(d, b), ")"]); },

  // RegExp replace.  This is interesting for the same reason as array extras.  Also, in SpiderMonkey, the "this" argument is weird (obj.__parent__?)
  function(d, b) { return cat(["'fafafa'", ".", "replace", "(", "/", "a", "/", "g", ", ", makeFunction(d, b), ")"]); },

  // Containment in an array or object (or, if this happens to end up on the LHS of an assignment, destructuring)
  function(d, b) { return cat(["[", makeExpr(d, b), "]"]); },
  function(d, b) { return cat(["(", "{", makeId(d, b), ": ", makeExpr(d, b), "}", ")"]); },

  // Functions: called immediately/not
  function(d, b) { return makeFunction(d, b); },
  function(d, b) { return makeFunction(d, b) + ".prototype"; },
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
  function(d, b) { return cat([makeLValue(d, b), Random.index(["|=", "%=", "+=", "-="]), makeExpr(d, b)]); },

  // Watchpoints (similar to setters)
  function(d, b) { return cat([makeExpr(d, b), ".", "watch", "(", makePropertyName(d, b), ", ", makeFunction(d, b), ")"]); },
  function(d, b) { return cat([makeExpr(d, b), ".", "unwatch", "(", makePropertyName(d, b), ")"]); },

  // ES5 getter/setter syntax, imperative (added in Gecko 1.9.3?)
  function(d, b) { return cat(["Object.defineProperty", "(", makeId(d, b), ", ", makePropertyName(d, b), ", ", makePropertyDescriptor(d, b), ")"]); },

  // Old getter/setter syntax, imperative
  function(d, b) { return cat([makeExpr(d, b), ".", "__defineGetter__", "(", uneval(makeId(d, b)), ", ", makeFunction(d, b), ")"]); },
  function(d, b) { return cat([makeExpr(d, b), ".", "__defineSetter__", "(", uneval(makeId(d, b)), ", ", makeFunction(d, b), ")"]); },
  function(d, b) { return cat(["this", ".", "__defineGetter__", "(", uneval(makeId(d, b)), ", ", makeFunction(d, b), ")"]); },
  function(d, b) { return cat(["this", ".", "__defineSetter__", "(", uneval(makeId(d, b)), ", ", makeFunction(d, b), ")"]); },

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

  // Test eval in various contexts. (but avoid clobbering eval)
  // Test the special "obj.eval" and "eval(..., obj)" forms.
  function(d, b) { return makeExpr(d, b) + ".eval(" + uneval(makeScriptForEval(d, b)) + ")"; },
  function(d, b) { return "eval(" + uneval(makeScriptForEval(d, b)) + ")"; },
  function(d, b) { return "eval(" + uneval(makeScriptForEval(d, b)) + ", " + makeExpr(d, b) + ")"; },

  // Uneval needs more testing than it will get accidentally.  No cat() because I don't want uneval clobbered (assigned to) accidentally.
  function(d, b) { return "(uneval(" + makeExpr(d, b) + "))"; },

  // Constructors.  No cat() because I don't want to screw with the constructors themselves, just call them.
  function(d, b) { return "new " + Random.index(constructors) + "(" + makeActualArgList(d, b) + ")"; },
  function(d, b) { return          Random.index(constructors) + "(" + makeActualArgList(d, b) + ")"; },

  // Unary Math functions
  function (d, b) { return "Math." + Random.index(unaryMathFunctions) + "(" + makeExpr(d, b)   + ")"; },
  function (d, b) { return "Math." + Random.index(unaryMathFunctions) + "(" + makeNumber(d, b) + ")"; },

  // Binary Math functions
  function (d, b) { return "Math." + Random.index(binaryMathFunctions) + "(" + makeExpr(d, b)   + ", " + makeExpr(d, b)   + ")"; },
  function (d, b) { return "Math." + Random.index(binaryMathFunctions) + "(" + makeExpr(d, b)   + ", " + makeNumber(d, b) + ")"; },
  function (d, b) { return "Math." + Random.index(binaryMathFunctions) + "(" + makeNumber(d, b) + ", " + makeExpr(d, b)   + ")"; },
  function (d, b) { return "Math." + Random.index(binaryMathFunctions) + "(" + makeNumber(d, b) + ", " + makeNumber(d, b) + ")"; },

  // Gecko wrappers
  function(d, b) { return "new XPCNativeWrapper(" + makeExpr(d, b) + ")"; },
  function(d, b) { return "new XPCSafeJSObjectWrapper(" + makeExpr(d, b) + ")"; },

  // Harmony proxy creation: object, function without constructTrap, function with constructTrap
  function(d, b) { return makeId(d, b) + " = " + "Proxy.create(" + makeProxyHandler(d, b) + ", " + makeExpr(d, b) + ")"; },
  function(d, b) { return makeId(d, b) + " = " + "Proxy.createFunction(" + makeProxyHandler(d, b) + ", " + makeFunction(d, b) + ")"; },
  function(d, b) { return makeId(d, b) + " = " + "Proxy.createFunction(" + makeProxyHandler(d, b) + ", " + makeFunction(d, b) + ", " + makeFunction(d, b) + ")"; },

  function(d, b) { return cat(["delete", " ", makeId(d, b), ".", makeId(d, b)]); },

  // Spidermonkey: global ES5 strict mode
  function(d, b) { return "(void options('strict_mode'))"; },

  // Spidermonkey: additional "strict" warnings, distinct from ES5 strict mode
  function(d, b) { return "(void options('strict'))"; },

  // Spidermonkey: versions
  function(d, b) { return "(void version(" + Random.index([170, 180, 185]) + "))"; },

  // More special Spidermonkey shell functions
  //  function(d, b) { return "dumpObject(" + makeExpr(d, b) + ")" } }, // crashes easily, bug 836603
  function(d, b) { return "(void findReferences(" + makeExpr(d, b) + "))"; },
  function(d, b) { return "(void shapeOf(" + makeExpr(d, b) + "))"; },
  function(d, b) { return "intern(" + makeExpr(d, b) + ")"; },
  function(d, b) { return "timeout(1800)"; }, // see https://bugzilla.mozilla.org/show_bug.cgi?id=840284#c12 -- replace when bug 831046 is fixed
  function(d, b) { return "(makeFinalizeObserver('tenured'))"; },
  function(d, b) { return "(makeFinalizeObserver('nursery'))"; },

  makeRegexUseExpr,
  makeShapeyValue,
  makeIterable,
  function(d, b) { return makeMathExpr(d + rnd(3), b); },
];


var fuzzTestingFunctions = fuzzTestingFunctionsCtor(!jsshell, fuzzTestingFunctionArg, fuzzTestingFunctionArg);

// Ensure that even if makeExpr returns "" or "1, 2", we only pass one argument to functions like schedulegc
// (null || (" + makeExpr(d - 2, b) + "))
// Darn, only |this| and local variables are safe: an expression with side effects breaks the statement-level compareJIT hack
function fuzzTestingFunctionArg(d, b) { return "this"; }

function makeTestingFunctionCall(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  var callStatement = Random.index(fuzzTestingFunctions.testingFunctions)(d, b);

  // Curly braces to make it less likely for unwanted return values to leak out
  // and confuse compareJIT.
  var callBlock = "{ " + callStatement + " }";

  if (jsshell && rnd(5) === 0) {
    // Differential testing hack!
    // The idea here: make compareJIT tell us when functions like gc() surprise
    // us with visible side effects.
    // * Functions in testing-functions.js are chosen to be ones with no visible
    //   side effects except for return values (voided) or throwing (caught).
    // * This condition is controlled by --no-asmjs, which compareJIT.py flips.
    //     (A more principled approach would be to have compareJIT set an environment
    //     variable and read it here using os.getenv(), but os is not available
    //     when running with --fuzzing-safe...)
    // * The extra braces prevent a stray "else" from being associated with this "if".
    // * The 'void 0' at the end ensures the last expression-statement is consistent
    //     (needed because |eval| returns that as its result)
    var cond = (rnd(2) ? "!" : "") + "isAsmJSCompilationAvailable()";
    return "{ if (" + cond + ") " + callBlock + " void 0; }";
  }

  return callBlock;
}


// SpiderMonkey shell (but not xpcshell) has an "evalcx" function and a "newGlobal" function.
// This tests sandboxes and cross-compartment wrappers.
if (typeof evalcx == "function") {
  exprMakers = exprMakers.concat([
    function(d, b) { return makeGlobal(d, b); },
    function(d, b) { return "evalcx(" + uneval(makeScriptForEval(d, b)) + ", " + makeExpr(d, b) + ")"; },
    function(d, b) { return "evalcx(" + uneval(makeScriptForEval(d, b)) + ", " + makeGlobal(d, b) + ")"; },
  ]);
}

function makeGlobal(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (rnd(10))
    return "this";

  var gs = Random.index([
    "evalcx('')",
    "evalcx('lazy')",
    "newGlobal({sameZoneAs: {}})", // same zone
    "newGlobal({sameZoneAs: " + makeExpr(d - 2, b) + "})", // other zone
    "newGlobal()", // new zone
  ]);

  if (rnd(2))
    gs = "fillShellSandbox(" + gs + ")";

  return gs;
}

if (xpcshell) {
  exprMakers = exprMakers.concat([
    function(d, b) { var n = rnd(4); return "newGeckoSandbox(" + n + ")"; },
    function(d, b) { var n = rnd(4); return "s" + n + " = newGeckoSandbox(" + n + ")"; },
    // Doesn't this need to be Components.utils.evalInSandbox? Oh well, we need to fix bug 613142 first.
    function(d, b) { var n = rnd(4); return "evalInSandbox(" + uneval(makeStatement(d, b)) + ", newGeckoSandbox(" + n + "))"; },
    function(d, b) { var n = rnd(4); return "evalInSandbox(" + uneval(makeStatement(d, b)) + ", s" + n + ")"; },
    function(d, b) { return "evalInSandbox(" + uneval(makeStatement(d, b)) + ", " + makeExpr(d, b) + ")"; },
    function(d, b) { return "(Components.classes ? quit() : gc()); }"; },
  ]);
}


function makeShapeyConstructor(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);
  var argName = uniqueVarName();
  var t = rnd(4) ? "this" : argName;
  var funText = "function shapeyConstructor(" + argName + "){" + directivePrologue();
  var bp = b.concat([argName]);

  var nPropNames = rnd(6) + 1;
  var propNames = [];
  for (var i = 0; i < nPropNames; ++i) {
    propNames[i] = makePropertyName(d, b);
  }

  var nStatements = rnd(11);
  for (var i = 0; i < nStatements; ++i) {
    var propName = Random.index(propNames);
    var tprop = t + "[" + propName + "]";
    if (rnd(5) === 0) {
      funText += "if (" + (rnd(2) ? argName : makeExpr(d, bp)) + ") ";
    }
    switch(rnd(8)) {
      case 0:  funText += "delete " + tprop + ";"; break;
      case 1:  funText += "Object.defineProperty(" + t + ", " + (rnd(2) ? propName : makePropertyName(d, b)) + ", " + makePropertyDescriptor(d, bp) + ");"; break;
      case 2:  funText += "{ " + makeStatement(d, bp) + " } "; break;
      case 3:  funText += tprop + " = " + makeExpr(d, bp)        + ";"; break;
      case 4:  funText += tprop + " = " + makeFunction(d, bp)    + ";"; break;
      case 5:  funText += "for (var ytq" + uniqueVarName() + " in " + t + ") { }"; break;
      case 6:  funText += "Object." + Random.index(["preventExtensions","seal","freeze"]) + "(" + t + ");"; break;
      default: funText += tprop + " = " + makeShapeyValue(d, bp) + ";"; break;
    }
  }
  funText += "return " + t + "; }";
  return funText;
}


var propertyNameMakers = Random.weighted([
  { w: 1,  v: function(d, b) { return makeExpr(d - 1, b); } },
  { w: 1,  v: function(d, b) { return maybeNeg() + rnd(20); } },
  { w: 1,  v: function(d, b) { return '"' + maybeNeg() + rnd(20) + '"'; } },
  { w: 1,  v: function(d, b) { return "new String(" + '"' + maybeNeg() + rnd(20) + '"' + ")"; } },
  { w: 5,  v: function(d, b) { return simpleSource(Random.index(specialProperties)); } },
  { w: 1,  v: function(d, b) { return simpleSource(makeId(d - 1, b)); } },
  { w: 5,  v: function(d, b) { return simpleSource(Random.index(allMethodNames)); } },
]);

function maybeNeg() { return rnd(5) ? "" : "-"; }

function makePropertyName(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  return (Random.index(propertyNameMakers))(d, b);
}

function makeShapeyConstructorLoop(d, b)
{
  var a = makeIterable(d, b);
  var v = makeNewId(d, b);
  var v2 = uniqueVarName(d, b);
  var bvv = b.concat([v, v2]);
  return makeShapeyConstructor(d - 1, b) +
    "/*tLoopC*/for each (let " + v + " in " + a + ") { " +
     "try{" +
       "let " + v2 + " = " + Random.index(["new ", ""]) + "shapeyConstructor(" + v + "); print('EETT'); " +
       //"print(uneval(" + v2 + "));" +
       makeStatement(d - 2, bvv) +
     "}catch(e){print('TTEE ' + e); }" +
  " }";
}


function makePropertyDescriptor(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  var s = "({";

  switch(rnd(3)) {
  case 0:
    // Data descriptor. Can have 'value' and 'writable'.
    if (rnd(2)) s += "value: " + makeExpr(d, b) + ", ";
    if (rnd(2)) s += "writable: " + makeBoolean(d, b) + ", ";
    break;
  case 1:
    // Accessor descriptor. Can have 'get' and 'set'.
    if (rnd(2)) s += "get: " + makeFunction(d, b) + ", ";
    if (rnd(2)) s += "set: " + makeFunction(d, b) + ", ";
    break;
  default:
  }

  if (rnd(2)) s += "configurable: " + makeBoolean(d, b) + ", ";
  if (rnd(2)) s += "enumerable: " + makeBoolean(d, b) + ", ";

  // remove trailing comma
  if (s.length > 2)
    s = s.substr(0, s.length - 2);

  s += "})";
  return s;
}

function makeBoolean(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);
  switch(rnd(4)) {
    case 0:   return "true";
    case 1:   return "false";
    case 2:   return makeExpr(d - 2, b);
    default:  var m = loopModulo(); return "(" + Random.index(b) + " % " + m + Random.index([" == ", " != "]) + rnd(m) + ")";
  }
}


function makeObjLiteralPart(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  switch(rnd(8))
  {
    // Literal getter/setter
    // Surprisingly, string literals, integer literals, and float literals are also good!
    // (See https://bugzilla.mozilla.org/show_bug.cgi?id=520696.)
    case 2: return cat([" get ", makeObjLiteralName(d, b), maybeName(d, b), "(", makeFormalArgList(d - 1, b), ")", makeFunctionBody(d, b)]);
    case 3: return cat([" set ", makeObjLiteralName(d, b), maybeName(d, b), "(", makeFormalArgList(d - 1, b), ")", makeFunctionBody(d, b)]);

    case 4: return "/*toXFun*/" + cat([Random.index(["toString", "toSource", "valueOf"]), ": ", makeToXFunction(d - 1, b)]);

    default: return cat([makeObjLiteralName(d, b), ": ", makeExpr(d, b)]);
  }
}

function makeToXFunction(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  switch(rnd(4)) {
    case 0:  return "function() { return " + makeExpr(d, b) + "; }";
    case 1:  return "function() { return this; }";
    case 2:  return makeEvilCallback(d, b);
    default: return makeFunction(d, b);
  }
}


function makeObjLiteralName(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  switch(rnd(6))
  {
    case 0:  return simpleSource(makeNumber(d, b)); // a quoted number
    case 1:  return makeNumber(d, b);
    case 2:  return Random.index(allPropertyNames);
    case 3:  return Random.index(specialProperties);
    default: return makeId(d, b);
  }
}


function makeFunction(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  d = d - 1;

  if(rnd(5) === 1)
    return makeExpr(d, b);

  if (rnd(4) === 1)
    return Random.index(builtinFunctions);

  return (Random.index(functionMakers))(d, b);
}


function maybeName(d, b)
{
  if (rnd(2) === 0)
    return " " + makeId(d, b) + " ";
  else
    return "";
}

function directivePrologue()
{
  var s = "";
  if (rnd(3) === 0)
    s += '"use strict"; ';
  if (rnd(30) === 0)
    s += '"use asm"; ';
  return s;
}

function makeFunctionBody(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  switch(rnd(5)) {
    case 0:  return cat([" { ", directivePrologue(), makeStatement(d - 1, b),   " } "]);
    case 1:  return cat([" { ", directivePrologue(), "return ", makeExpr(d, b), " } "]);
    case 2:  return cat([" { ", directivePrologue(), "yield ",  makeExpr(d, b), " } "]);
    case 3:  return '"use asm"; ' + asmJSInterior([]);
    default: return makeExpr(d, b); // make an "expression closure"
  }
}


var functionMakers = [
  // Note that a function with a name is sometimes considered a statement rather than an expression.

  makeFunOnCallChain,
  makeMathFunction,
  makeMathyFunRef,

  // Functions and expression closures
  function(d, b) { var v = makeNewId(d, b); return cat(["function", " ", maybeName(d, b), "(", v,                       ")", makeFunctionBody(d, b.concat([v]))]); },
  function(d, b) {                          return cat(["function", " ", maybeName(d, b), "(", makeFormalArgList(d, b), ")", makeFunctionBody(d, b)]); },

  // Arrow functions with one argument (no parens needed) (no destructuring allowed in this form?)
  function(d, b) { var v = makeNewId(d, b); return cat([     v,                            " => ", makeFunctionBody(d, b.concat([v]))]); },

  // Arrow functions with multiple arguments
  function(d, b) {                          return cat(["(", makeFormalArgList(d, b), ")", " => ", makeFunctionBody(d, b)]); },

  // The identity function
  function(d, b) { return "function(q) { " + directivePrologue() + "return q; }"; },
  function(d, b) { return "q => q"; },

  // A function that does something
  function(d, b) { return "function(y) { " + directivePrologue() + makeStatement(d, b.concat(["y"])) + " }"; },

  // A function that computes something
  function(d, b) { return "function(y) { " + directivePrologue() + "return " + makeExpr(d, b.concat(["y"])) + " }"; },

  // A generator that does something
  function(d, b) { return "function(y) { " + directivePrologue() + "yield y; " + makeStatement(d, b.concat(["y"])) + "; yield y; }"; },

  // A generator expression -- kinda a function??
  function(d, b) { return "(1 for (x in []))"; },

  // A simple wrapping pattern
  function(d, b) { return "/*wrap1*/(function(){ " + directivePrologue() + makeStatement(d, b) + "return " + makeFunction(d, b) + "})()"; },

  // Wrapping with upvar: escaping, may or may not be modified
  function(d, b) { var v1 = uniqueVarName(); var v2 = uniqueVarName(); return "/*wrap2*/(function(){ " + directivePrologue() + "var " + v1 + " = " + makeExpr(d, b) + "; var " + v2 + " = " + makeFunction(d, b.concat([v1])) + "; return " + v2 + ";})()"; },

  // Wrapping with upvar: non-escaping
  function(d, b) { var v1 = uniqueVarName(); var v2 = uniqueVarName(); return "/*wrap3*/(function(){ " + directivePrologue() + "var " + v1 + " = " + makeExpr(d, b) + "; (" + makeFunction(d, b.concat([v1])) + ")(); })"; },

  // Apply, call
  function(d, b) { return "(" + makeFunction(d-1, b) + ").apply"; },
  function(d, b) { return "(" + makeFunction(d-1, b) + ").call"; },

  // Bind
  function(d, b) { return "(" + makeFunction(d-1, b) + ").bind"; },
  function(d, b) { return "(" + makeFunction(d-1, b) + ").bind(" + makeActualArgList(d, b) + ")"; },

  // Methods with known names
  function(d, b) { return cat([makeExpr(d, b), ".", Random.index(allMethodNames)]); },

  // Special functions that might have interesting results, especially when called "directly" by things like string.replace or array.map.
  function(d, b) { return "eval"; }, // eval is interesting both for its "no indirect calls" feature and for the way it's implemented in spidermonkey (a special bytecode).
  function(d, b) { return "(let (e=eval) e)"; },
  function(d, b) { return "new Function"; }, // this won't be interpreted the same way for each caller of makeFunction, but that's ok
  function(d, b) { return "(new Function(" + uneval(makeStatement(d, b)) + "))"; },
  function(d, b) { return "Function"; }, // without "new"
  function(d, b) { return "decodeURI"; },
  function(d, b) { return "decodeURIComponent"; },
  function(d, b) { return "encodeURI"; },
  function(d, b) { return "encodeURIComponent"; },
  function(d, b) { return "neuter"; },
  function(d, b) { return "objectEmulatingUndefined"; }, // spidermonkey shell object like the browser's document.all
  function(d, b) { return "XPCNativeWrapper"; },
  function(d, b) { return "XPCSafeJSObjectWrapper"; },
  function(d, b) { return makeProxyHandlerFactory(d, b); },
  function(d, b) { return makeShapeyConstructor(d, b); },
  function(d, b) { return Random.index(typedArrayConstructors); },
  function(d, b) { return Random.index(constructors); },
];

var typedArrayConstructors = [
  "Int8Array",
  "Uint8Array",
  "Int16Array",
  "Uint16Array",
  "Int32Array",
  "Uint32Array",
  "Float32Array",
  "Float64Array",
  "Uint8ClampedArray"
];

function makeTypedArrayStatements(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (d < 0) return "";

  var numViews = rnd(d) + 1;
  var numExtraStatements = rnd(d) + 1;
  var buffer = uniqueVarName();
  var bufferSize = (1 + rnd(2)) * (1 + rnd(2)) * (1 + rnd(2)) * rnd(5);
  var statements = "var " + buffer + " = new " + arrayBufferType() + "(" + bufferSize + "); ";
  var bv = b.concat([buffer]);
  for (var j = 0; j < numViews; ++j) {
    var view = buffer + "_" + j;
    var type = Random.index(typedArrayConstructors);
    statements += "var " + view + " = new " + type + "(" + buffer + "); ";
    bv.push(view);
    var view_0 = view + "[0]";
    bv.push(view_0);
    if (rnd(3) === 0)
      statements += "print(" + view_0 + "); ";
    if (rnd(3))
      statements += view_0 + " = " + makeNumber(d - 2, b) + "; ";
    bv.push(view + "[" + rnd(11) + "]");
  }
  for (var j = 0; j < numExtraStatements; ++j) {
    statements += makeStatement(d - numExtraStatements, bv);
  }
  return statements;
}

function makeNumber(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  var signStr = rnd(2) ? "-" : "";

  switch(rnd(70)) {
    case 0:  return makeExpr(d - 2, b);
    case 1:  return signStr + "0";
    case 2:  return signStr + (rnd(1000) / 1000);
    case 3:  return signStr + (rnd(0xffffffff) / 2);
    case 4:  return signStr + rnd(0xffffffff);
    case 5:  return Random.index(["0.1", ".2", "3", "1.3", "4.", "5.0000000000000000000000", "1.2e3", "1e81", "1e+81", "1e-81", "1e4", "0", "-0", "(-0)", "-1", "(-1)", "0x99", "033", "3.141592653589793", "3/0", "-3/0", "0/0", "0x2D413CCC", "0x5a827999", "0xB504F332", "(0x50505050 >> 1)", "0x80000000"]);
    case 6:  return signStr + (Math.pow(2, rnd(66)) + (rnd(3) - 1));
    default: return signStr + rnd(30);
  }
}


function makeLetHead(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  var items = (d > 0 || rnd(2) === 0) ? rnd(10) + 1 : 1;
  var result = "";

  for (var i = 0; i < items; ++i) {
    if (i > 0)
      result += ", ";
    result += makeLetHeadItem(d - i, b);
  }

  return result;
}

function makeLetHeadItem(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  d = d - 1;

  if (d < 0 || rnd(2) === 0)
    return rnd(2) ? uniqueVarName() : makeId(d, b);
  else if (rnd(5) === 0)
    return makeDestructuringLValue(d, b) + " = " + makeExpr(d, b);
  else
    return makeId(d, b) + " = " + makeExpr(d, b);
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

  var argList = [];

  var nArgs = rnd(5) ? rnd(3) : rnd(100);
  for (var i = 0; i < nArgs; ++i) {
    argList.push(makeFormalArg(d - i, b));
  }

  if (rnd(5) === 0) {
    // https://developer.mozilla.org/en-US/docs/JavaScript/Reference/rest_parameters
    argList.push("..." + makeId(d, b));
  }

  return argList.join(", ");
}

function makeFormalArg(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (rnd(8) === 1)
    return makeDestructuringLValue(d, b);

  return makeId(d, b) + (rnd(5) ? "" : " = " + makeExpr(d, b));
}


function makeNewId(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  return Random.index(["a", "b", "c", "d", "e", "w", "x", "y", "z"]);
}

function makeId(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (rnd(3) === 1 && b.length)
    return Random.index(b);

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
    return Random.index(["get", "set", "getter", "setter", "delete", "let", "yield", "each"]);
  case 11: case 12: case 13:
    return "this." + makeId(d, b);
  case 14: case 15: case 16:
    return makeObjLiteralName(d - 1, b);
  case 17: case 18:
    return makeId(d - 1, b);
  case 19:
    return " "; // [k, v] becomes [, v] -- test how holes are handled in unexpected destructuring
  case 20:
    return "this";
  }

  return Random.index(["a", "b", "c", "d", "e", "w", "x", "y", "z",
                 "window", "eval", "\u3056", "NaN",
//                 "valueOf", "toString", // e.g. valueOf getter :P // bug 381242, etc
                  ]);

  // window is a const (in the browser), so some attempts to redeclare it will cause errors

  // eval is interesting because it cannot be called indirectly. and maybe also because it has its own opcode in jsopcode.tbl.
  // but bad things happen if you have "eval setter". so let's not put eval in this list.
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
    return cat([" for ",          "(", makeForInLHS(d, b), " in ", makeExpr(d - 2, b),     ")"]) + makeComprehension(d - 1, b);
  case 2:
    return cat([" for ", "each ", "(", makeId(d, b),       " in ", makeExpr(d - 2, b),     ")"]) + makeComprehension(d - 1, b);
  case 3:
    return cat([" for ", "each ", "(", makeId(d, b),       " in ", makeIterable(d - 2, b), ")"]) + makeComprehension(d - 1, b);
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
//  if (version() == 170 && rnd(4) === 0)
//    return cat(["[", makeLValue(d, b), ", ", makeLValue(d, b), "]"]);

  return makeLValue(d, b);
}


function makeLValue(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (d <= 0 || (rnd(2) === 1))
    return makeId(d - 1, b);

  d = rnd(d); // !

  return (Random.index(lvalueMakers))(d, b);
}


var lvalueMakers = [
  // Simple variable names :)
  function(d, b) { return cat([makeId(d, b)]); },

  // Parenthesized lvalues
  function(d, b) { return cat(["(", makeLValue(d, b), ")"]); },

  // Destructuring
  function(d, b) { return makeDestructuringLValue(d, b); },
  function(d, b) { return "(" + makeDestructuringLValue(d, b) + ")"; },

  // Certain functions can act as lvalues!  See JS_HAS_LVALUE_RETURN in js engine source.
  function(d, b) { return cat([makeId(d, b), "(", makeExpr(d, b), ")"]); },
  function(d, b) { return cat(["(", makeExpr(d, b), ")", "(", makeExpr(d, b), ")"]); },

  // Builtins
  function(d, b) { return Random.index(builtinProperties); },
  function(d, b) { return Random.index(builtinObjectNames); },

  // Arguments object, which can alias named parameters to the function
  function(d, b) { return "arguments"; },
  function(d, b) { return cat(["arguments", "[", makePropertyName(d, b), "]"]); },
  function(d, b) { return makeFunOnCallChain(d, b) + ".arguments"; }, // read-only arguments object

  // Property access / index into array
  function(d, b) { return cat([makeExpr(d, b),  ".", makeId(d, b)]); },
  function(d, b) { return cat([makeExpr(d, b),  ".", "__proto__"]); },
  function(d, b) { return cat([makeExpr(d, b), "[", makePropertyName(d, b), "]"]); },

  // Throws, but more importantly, tests js_DecompileValueGenerator in various contexts.
  function(d, b) { return "this.zzz.zzz"; },

  // Intentionally bogus, but not quite garbage.
  function(d, b) { return makeExpr(d, b); },
];


function makeDestructuringLValue(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  d = d - 1;

  if (d < 0 || rnd(4) === 1)
    return makeId(d, b);

  if (rnd(6) === 1)
    return makeLValue(d, b);

  return (Random.index(destructuringLValueMakers))(d, b);
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
  if (rnd(2) === 0)
    return "";

  return makeDestructuringLValue(d, b);
}



function makeTerm(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  return (Random.index(termMakers))(d, b);
}

var termMakers = [
  // Variable names
  function(d, b) { return makeId(d, b); },

  // Simple literals (no recursion required to make them)
  function(d, b) { return Random.index([
    // Arrays
    "[]", "[1]", "[[]]", "[[1]]", "[,]", "[,,]", "[1,,]",
    // Objects
    "{}", "({})", "({a1:1})",
    // Possibly-destructuring arrays
    "[z1]", "[z1,,]", "[,,z1]",
    // Possibly-destructuring objects
    "({a2:z2})",
    "function(id) { return id }",
    "function ([y]) { }",
    "(function ([y]) { })()",

    "arguments",
    "Math",
    "this",
    "length",

    '"\u03A0"', // unicode not escaped
    ]);
  },
  makeNumber,
  function(d, b) { return Random.index([ "true", "false", "undefined", "null"]); },
  function(d, b) { return Random.index([ "this", "window" ]); },
  function(d, b) { return Random.index([" \"\" ", " '' "]); },
  randomUnitStringLiteral, // unicode escaped
  function(d, b) { return Random.index([" /x/ ", " /x/g "]); },
  makeRegex,
];

function randomUnitStringLiteral()
{
  var s = "\"\\u";
  for (var i = 0; i < 4; ++i) {
    s += "0123456789ABCDEF".charAt(rnd(16));
  }
  s += "\"";
  return s;
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
  if (rnd(3) === 0) {
    return String.fromCharCode(32 + rnd(128 - 32));
  }
  if (rnd(6) === 0) {
    return String.fromCharCode(rnd(65536));
  }

  return Random.index([

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
  "...", "=>",

  // most real keywords plus a few reserved keywords
  " in ", " instanceof ", " let ", " new ", " get ", " for ", " if ", " else ", " else if ", " try ", " catch ", " finally ", " export ", " import ", " void ", " with ",
  " default ", " goto ", " case ", " switch ", " do ", " /*infloop*/while ", " return ", " yield ", " break ", " continue ", " typeof ", " var ", " const ",

  // reserved when found in strict mode code
  " package ",

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


function makeShapeyValue(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (rnd(10) === 0)
    return makeExpr(d, b);

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

    // String literals
    [" \"\" ", " '' ", " 'A' ", " '\\0' ", ' "use strict" '],

    // Regular expression literals
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
    [ "function(){}" ],
    [ "{}", "[]", "[1]", "['z']", "[undefined]", "this", "eval", "arguments", "arguments.caller", "arguments.callee" ],
    [ "objectEmulatingUndefined()" ],

    // Actual variables (slightly dangerous)
    [ b.length ? Random.index(b) : "x" ]
  ];

  return Random.index(Random.index(a));
}

function mixedTypeArrayElem(d, b)
{
  while (true) {
    var s = makeShapeyValue(d - 3, b);
    if (s.length < 60)
      return s;
  }
}

function makeMixedTypeArray(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  // Pick two to five values to use as array entries.
  var q = rnd(4) + 2;
  var picks = [];
  for (var j = 0; j < q; ++j) {
    picks.push(mixedTypeArrayElem(d, b));
  }

  // Create a large array literal by randomly repeating the values.
  var c = [];
  var count = loopCount();
  for (var j = 0; j < count; ++j) {
    var elem = Random.index(picks);
    // Sometimes, especially at the beginning of arrays, repeat a single value (or type) many times
    // (This is needed for shape warmup, but not for JIT warmup)
    var repeat = count === 0 ? rnd(4)===0 : rnd(50)===0;
    var repeats = repeat ? rnd(30) : 1;
    for (var k = 0; k < repeats; ++k) {
      c.push(elem);
    }
  }

  return "/*MARR*/" + "[" + c.join(", ") + "]";
}

function makeArrayLiteral(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (rnd(2) === 0)
    return makeMixedTypeArray(d, b);

  var elems = [];
  while (rnd(5)) elems.push(makeArrayLiteralElem(d, b));
  return "/*FARR*/" + "[" + elems.join(", ") + "]";
}

function makeArrayLiteralElem(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  switch (rnd(5)) {
    case 0:  return "..." + makeIterable(d - 1, b); // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Spread_operator
    case 1:  return ""; // hole
    default: return makeExpr(d - 1, b);
  }
}

function makeIterable(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  if (d < 1)
    return "[]";

  return (Random.index(iterableExprMakers))(d, b);
}

var iterableExprMakers = Random.weighted([
  // Arrays
  { w: 1, v: function(d, b) { return "new Array(" + makeNumber(d, b) + ")"; } },
  { w: 8, v: makeArrayLiteral },

  // Array comprehensions (JavaScript 1.7)
  { w: 1, v: function(d, b) { return cat(["[", makeExpr(d, b), makeComprehension(d, b), "]"]); } },

  // Generator expressions (JavaScript 1.8)
  { w: 1, v: function(d, b) { return cat([     makeExpr(d, b), makeComprehension(d, b)     ]); } },
  { w: 1, v: function(d, b) { return cat(["(", makeExpr(d, b), makeComprehension(d, b), ")"]); } },

  // A generator that yields once
  { w: 1, v: function(d, b) { return "(function() { " + directivePrologue() + "yield " + makeExpr(d - 1, b) + "; } })()"; } },
  // A pass-through generator
  { w: 1, v: function(d, b) { return "/*PTHR*/(function() { " + directivePrologue() + "for (var i of " + makeIterable(d - 1, b) + ") { yield i; } })()"; } },

  { w: 1, v: makeFunction },
  { w: 1, v: makeExpr },
]);

function strTimes(s, n)
{
  if (n == 0) return "";
  if (n == 1) return s;
  var s2 = s + s;
  var r = n % 2;
  var d = (n - r) / 2;
  var m = strTimes(s2, d);
  return r ? m + s : m;
}


function makeAsmJSModule(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  var interior = asmJSInterior([]);
  return '(function(stdlib, foreign, heap){ "use asm"; ' + interior + ' })';
}

function makeAsmJSFunction(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  var interior = asmJSInterior(["ff"]);
  return '(function(stdlib, foreign, heap){ "use asm"; ' + interior + ' })(this, {ff: ' + makeFunction(d - 2, b) + '}, new ' + arrayBufferType() + '(4096))';
}

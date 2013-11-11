
/***********************
 * TEST BUILT-IN TYPES *
 ***********************/

var makeBuilderStatement;
var makeEvilCallback;

(function setUpBuilderStuff() {
  var ARRAY_SIZE = 20;
  var OBJECTS_PER_TYPE = 3;
  var smallPowersOfTwo = [1, 2, 4, 8]; // The largest typed array views are 64-bit aka 8-byte
  function bufsize() { return rnd(ARRAY_SIZE) * Random.index(smallPowersOfTwo); }

  // Emit a variable name for type-abbreviation t.
  function m(t)
  {
    if (!t)
      t = "aosmevbtihgfp";
    t = t.charAt(rnd(t.length));
    var name = t + rnd(OBJECTS_PER_TYPE);
    switch(rnd(16)) {
      case 0:  return m("o") + "." + name;
      case 1:  return m("g") + "." + name;
      case 2:  return "this." + name;
      default: return name;
    }
  }

  function val(d, b)
  {
    if (rnd(10))
      return m();
    return makeExpr(d, b);
  }

  // Emit an assignment (or a roughly-equivalent getter)
  function assign(d, b, t, rhs)
  {
    switch(rnd(18)) {
    // Could have two forms of the getter: one that computes it each time on demand, and one that computes a constant-function closure
    case 0:  return (
      "Object.defineProperty(" +
        (rnd(8)?"this":m("og")) + ", " +
        simpleSource(m(t)) + ", " +
        "{ " + propertyDescriptorPrefix(d-1, b) + " get: function() { " + (rnd(8)?"":makeBuilderStatement(d-1,b)) + " return " + rhs + "; } }" +
      ");"
    );
    case 1:  return Random.index(varBinder) + m(t) + " = " + rhs + ";";
    default: return m(t) + " = " + rhs + ";";
    }
  }

  function makeCounterClosure(d, b)
  {
    // A closure with a counter. Do stuff depending on the counter.
    var v = uniqueVarName();
    var infrequently = infrequentCondition(v, 10);
    return (
      "(function mcc_() { " +
        "var " + v + " = 0; " +
        "return function() { " +
          "++" + v + "; " +
            (rnd(3) ?
              "if (" + infrequently + ") { dumpln('hit!'); " + makeBuilderStatement(d - 1, b) + makeBuilderStatement(d - 1, b) + " } " +
              "else { dumpln('miss!'); " + makeBuilderStatement(d - 1, b) + makeBuilderStatement(d - 1, b) + " } "
            : m("f") + "(" + infrequently + ");"
            ) +
        "};" +
      "})()");
  }

  function fdecl(d, b)
  {
    var argName = m();
    var bv = b.concat([argName]);
    return "function " + m("f") + "(" + argName + ") " + makeFunctionBody(d, bv);
  }

  var builderFunctionMakers = weighted([
    { w: 9,  fun: function(d, b) { return "(function() { " + makeBuilderStatement(d - 1, b) + " return " + m() + "; })"; } },
    { w: 1,  fun: function(d, b) { return "(function() { " + makeBuilderStatement(d - 1, b) + " throw " + m() + "; })"; } },
    { w: 1,  fun: function(d, b) { return "(function(j) { " + m("f") + "(j); })"; } }, // a function that just makes one call is begging to be inlined
    // The following pair create and use boolean-using functions.
    { w: 4,  fun: function(d, b) { return "(function(j) { if (j) { " + makeBuilderStatement(d - 1, b) + " } else { " + makeBuilderStatement(d - 1, b) + " } })"; } },
    { w: 4,  fun: function(d, b) { return "(function() { for (var j=0;j<" + loopCount() + ";++j) { " + m("f") + "(j%"+(2+rnd(4))+"=="+rnd(2)+"); } })"; } },
    { w: 1,  fun: function(d, b) { return Random.index(builtinFunctions) + ".bind(" + m() + ")"; } },
    { w: 5,  fun: function(d, b) { return m("f"); } },
    { w: 3,  fun: makeCounterClosure },
    { w: 2,  fun: makeFunction },
    { w: 1,  fun: makeAsmJSModule },
    { w: 1,  fun: makeAsmJSFunction },
    { w: 1,  fun: makeRegisterStompFunction },
  ]);
  makeEvilCallback = function(d, b) {
    return (Random.index(builderFunctionMakers))(d - 1, b);
  };

  var handlerTraps = ["getOwnPropertyDescriptor", "getPropertyDescriptor", "defineProperty", "getOwnPropertyNames", "delete", "fix", "has", "hasOwn", "get", "set", "iterate", "enumerate", "keys"];

  function forwardingHandler(d, b) {
    return (
      "({"+
        "getOwnPropertyDescriptor: function(name) { Z; var desc = Object.getOwnPropertyDescriptor(X); desc.configurable = true; return desc; }, " +
        "getPropertyDescriptor: function(name) { Z; var desc = Object.getPropertyDescriptor(X); desc.configurable = true; return desc; }, " +
        "defineProperty: function(name, desc) { Z; Object.defineProperty(X, name, desc); }, " +
        "getOwnPropertyNames: function() { Z; return Object.getOwnPropertyNames(X); }, " +
        "delete: function(name) { Z; return delete X[name]; }, " +
        "fix: function() { Z; if (Object.isFrozen(X)) { return Object.getOwnProperties(X); } }, " +
        "has: function(name) { Z; return name in X; }, " +
        "hasOwn: function(name) { Z; return Object.prototype.hasOwnProperty.call(X, name); }, " +
        "get: function(receiver, name) { Z; return X[name]; }, " +
        "set: function(receiver, name, val) { Z; X[name] = val; return true; }, " +
        "iterate: function() { Z; return (function() { for (var name in X) { yield name; } })(); }, " +
        "enumerate: function() { Z; var result = []; for (var name in X) { result.push(name); }; return result; }, " +
        "keys: function() { Z; return Object.keys(X); } " +
      "})"
    )
    .replace(/X/g, m())
    .replace(/Z/g, function() {
      switch(rnd(20)){
        case 0:  return "return " + m();
        case 1:  return "throw " + m();
        default: return makeBuilderStatement(d - 2, b);
      }
    });
  }

  function propertyDescriptorPrefix(d, b)
  {
    return "configurable: " + makeBoolean(d, b) + ", " + "enumerable: " + makeBoolean(d, b) + ", ";
  }

  function strToEval(d, b)
  {
    switch(rnd(4)) {
      case 0:  return simpleSource(fdecl(d, b));
      case 1:  return simpleSource(makeBuilderStatement(d, b));
      case 2:  return simpleSource(makeExpr(d, b));
      default: return simpleSource(makeStatement(d, b));
    }
  }

  var initializedEverything = false;
  function initializeEverything(d, b)
  {
    if (initializedEverything)
      return ";";
    initializedEverything = true;

    var s = "";
    for (var i = 0; i < OBJECTS_PER_TYPE; ++i) {
      s += "a" + i + " = []; ";
      s += "o" + i + " = {}; ";
      s += "s" + i + " = ''; ";
      s += "r" + i + " = /x/; ";
      s += "g" + i + " = " + makeGlobal(d, b) + "; ";
      s += "f" + i + " = function(){}; ";
      s += "m" + i + " = new WeakMap; ";
      s += "e" + i + " = new Set; ";
      s += "v" + i + " = null; ";
      s += "b" + i + " = new ArrayBuffer(64); ";
      s += "t" + i + " = new Uint8ClampedArray; ";
      // don't initialize p (ParallelArray) here because we don't want initializeEverything to trip consistency exclusions
      // nothing for iterators, handlers
    }
    return s;
  }

  var builderStatementMakers = weighted([
    // a: Array
    { w: 1,  fun: function(d, b) { return assign(d, b, "a", "[]"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "a", "new Array"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "a", makeIterable(d, b)); } },
    { w: 1,  fun: function(d, b) { return m("a") + ".length = " + rnd(ARRAY_SIZE) + ";"; } },
    { w: 8,  fun: function(d, b) { return assign(d, b, "v", m("at") + ".length"); } },
    { w: 4,  fun: function(d, b) { return m("at") + "[" + rnd(ARRAY_SIZE) + "]" + " = " + val(d, b) + ";"; } },
    { w: 4,  fun: function(d, b) { return val(d, b) + " = " + m("at") + "[" + rnd(ARRAY_SIZE) + "]" + ";"; } },
    { w: 4,  fun: function(d, b) { return "/*ADP*/Object.defineProperty(" + m("at") + ", " + rnd(ARRAY_SIZE) + ", { " + propertyDescriptorPrefix(d, b) + "get: " + makeEvilCallback(d,b) + ", set: " + makeEvilCallback(d, b) + " });"; } },
    { w: 4,  fun: function(d, b) { return "/*ADP*/Object.defineProperty(" + m("at") + ", " + rnd(ARRAY_SIZE) + ", { " + propertyDescriptorPrefix(d, b) + "writable: " + makeBoolean(d,b) + ", value: " + val(d, b) + " });"; } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "a", makeFunOnCallChain(d, b) + ".arguments"); } }, // a read-only arguments object
    { w: 1,  fun: function(d, b) { return assign(d, b, "a", "arguments"); } }, // a read-write arguments object

    // Array pokage
    { w: 3,  fun: function(d, b) { return m("a") + "[0] = " + makeExpr(d, b); } },
    { w: 3,  fun: function(d, b) { return m("a") + "[1] = " + makeExpr(d, b); } },
    // Array mutators
    { w: 5,  fun: function(d, b) { return "Array.prototype.push.call("    + m("a") + ", " + val(d, b) + ");"; } },
    { w: 5,  fun: function(d, b) { return "Array.prototype.pop.call("     + m("a") + ");"; } },
    { w: 5,  fun: function(d, b) { return "Array.prototype.unshift.call(" + m("a") + ", " + val(d, b) + ");"; } },
    { w: 5,  fun: function(d, b) { return "Array.prototype.shift.call("   + m("a") + ");"; } },
    { w: 3,  fun: function(d, b) { return "Array.prototype.reverse.call(" + m("a") + ");"; } },
    { w: 3,  fun: function(d, b) { return "Array.prototype.sort.call("    + m("a") + ", " + makeEvilCallback(d, b) + ");"; } },
    { w: 1,  fun: function(d, b) { return "Array.prototype.splice.call("  + m("a") + ", " + (rnd(ARRAY_SIZE) - rnd(ARRAY_SIZE)) + ", " + rnd(ARRAY_SIZE) + ");" ; } },

    // Array accessors
    { w: 1,  fun: function(d, b) { return assign(d, b, "s", m("a") + ".join('')"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "s", m("a") + ".join(', ')"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "a", m("a") + ".concat(" + m("at") + ")"); } }, // can actually take multiple arrays
    { w: 1,  fun: function(d, b) { return assign(d, b, "a", m("a") + ".slice(" + (rnd(ARRAY_SIZE) - rnd(ARRAY_SIZE)) + ", " + (rnd(ARRAY_SIZE) - rnd(ARRAY_SIZE)) + ")"); } },
    // Array iterators
    { w: 3,  fun: function(d, b) { return "Array.prototype." + Random.index(["filter", "forEach", "every", "map", "some"]) + ".call(" + m("a") + ", " + makeEvilCallback(d, b) + ");"; } },
    { w: 3,  fun: function(d, b) { return "Array.prototype." + Random.index(["reduce, reduceRight"]) + ".call(" + m("a") + ", " + makeEvilCallback(d, b) + ");"; } },
    { w: 3,  fun: function(d, b) { return "Array.prototype." + Random.index(["reduce, reduceRight"]) + ".call(" + m("a") + ", " + makeEvilCallback(d, b) + ", " + m() + ");"; } },

    // p: ParallelArray
    // A parallel array can be constructed from (1) an array-like that has a length property, or (2) a length [possibly multi-dimensional] and elemental function
    { w: 1,  fun: function(d, b) { return assign(d, b, "p", "new ParallelArray(" + m("at") + ")"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "p", "new ParallelArray(" + makeParallelArraySizeAndInitializer(d, b) + ")"); } },
    // Parallel arrays are immutable, but have some readable properties
    { w: 3,  fun: function(d, b) { return assign(d, b, "a", m("p") + ".shape"); } }, // what
    // Parallel arrays have functional methods that will sometimes run in parallel.
    { w: 3,  fun: function(d, b) { return assign(d, b, "v", m("p") + ".get(" + m("v") + ")"); } },
    { w: 3,  fun: function(d, b) { return assign(d, b, "v", m("p") + ".get([" + m("v") + ", " + m("v") + "])"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "p", m("p") + ".map(" + Random.index(["1, ", "2, ", ""]) + (rnd(2)?m("f"):makeParallelMap(d,b)) + ")"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "p", m("p") + ".filter(" + (rnd(2)?m("f"):makeParallelFilter(d,b)) + ")"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "v", m("p") + ".reduce(" + (rnd(2)?m("f"):makeParallelBinary(d,b)) + ")"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "p", m("p") + ".scan(" +   (rnd(2)?m("f"):makeParallelBinary(d,b)) + ")"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "p", m("p") + ".scatter([0,0,1,1,2,2], undefined," + (rnd(2)?m("f"):makeParallelBinary(d,b)) + ")"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "p", m("p") + ".flatten()"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "p", m("p") + ".partition(" + (rnd(2)?m("v"):rnd(10)) + ")"); } },

    // o: Object
    { w: 1,  fun: function(d, b) { return assign(d, b, "o", "{}"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "o", "new Object"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "o", "Object.create(" + val(d, b) + ")"); } },
    { w: 3,  fun: function(d, b) { return "selectforgc(" + m("o") + ");"; } },

    // s: String
    { w: 1,  fun: function(d, b) { return assign(d, b, "s", "''"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "s", "new String"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "s", "new String(" + m() + ")"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "s", m("s") + ".charAt(" + rnd(ARRAY_SIZE) + ")"); } },
    { w: 5,  fun: function(d, b) { return m("s") + " += 'x';"; } },
    { w: 5,  fun: function(d, b) { return m("s") + " += " + m("s") + ";"; } },
    // Should add substr, substring, replace

    // m: Map, WeakMap
    { w: 1,  fun: function(d, b) { return assign(d, b, "m", "new Map"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "m", "new Map(" + m() + ")"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "m", "new WeakMap"); } },
    { w: 5,  fun: function(d, b) { return m("m") + ".has(" + val(d, b) + ");"; } },
    { w: 4,  fun: function(d, b) { return m("m") + ".get(" + val(d, b) + ");"; } },
    { w: 1,  fun: function(d, b) { return assign(d, b, null, m("m") + ".get(" + val(d, b) + ")"); } },
    { w: 5,  fun: function(d, b) { return m("m") + ".set(" + val(d, b) + ", " + val(d, b) + ");"; } },
    { w: 3,  fun: function(d, b) { return m("m") + ".delete(" + val(d, b) + ");"; } },

    // e: Set
    { w: 1,  fun: function(d, b) { return assign(d, b, "e", "new Set"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "e", "new Set(" + m() + ")"); } },
    { w: 5,  fun: function(d, b) { return m("e") + ".has(" + val(d, b) + ");"; } },
    { w: 5,  fun: function(d, b) { return m("e") + ".add(" + val(d, b) + ");"; } },
    { w: 3,  fun: function(d, b) { return m("e") + ".delete(" + val(d, b) + ");"; } },

    // b: Buffer
    { w: 1,  fun: function(d, b) { return assign(d, b, "b", "new ArrayBuffer(" + bufsize() + ")"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "b", m("t") + ".buffer"); } },

    // t: Typed arrays, aka ArrayBufferViews
    // Can be constructed using a length, typed array, sequence (e.g. array), or buffer with optional offsets!
    { w: 1,  fun: function(d, b) { return assign(d, b, "t", "new " + Random.index(typedArrayConstructors) + "(" + rnd(ARRAY_SIZE) + ")"); } },
    { w: 3,  fun: function(d, b) { return assign(d, b, "t", "new " + Random.index(typedArrayConstructors) + "(" + m("abt") + ")"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "t", "new " + Random.index(typedArrayConstructors) + "(" + m("b") + ", " + bufsize() + ", " + rnd(ARRAY_SIZE) + ")"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "t", m("t") + ".subarray(" + rnd(ARRAY_SIZE) + ")"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "t", m("t") + ".subarray(" + rnd(ARRAY_SIZE) + ", " + rnd(ARRAY_SIZE) + ")"); } },
    { w: 3,  fun: function(d, b) { return m("t") + ".set(" + m("at") + ", " + rnd(ARRAY_SIZE) + ");"; } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "v", m("tb") + ".byteLength"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "v", m("t") + ".byteOffset"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "v", m("t") + ".BYTES_PER_ELEMENT"); } },

    // h: proxy handler
    { w: 1,  fun: function(d, b) { return assign(d, b, "h", "{}"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "h", forwardingHandler(d, b)); } },
    { w: 1,  fun: function(d, b) { return "delete " + m("h") + "." + Random.index(handlerTraps) + ";"; } },
    { w: 4,  fun: function(d, b) { return m("h") + "." + Random.index(handlerTraps) + " = " + makeEvilCallback(d, b) + ";"; } },
    { w: 4,  fun: function(d, b) { return m("h") + "." + Random.index(handlerTraps) + " = " + m("f") + ";"; } },
    { w: 1,  fun: function(d, b) { return assign(d, b, null, "Proxy.create(" + m("h") + ", " + m() + ")"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "f", "Proxy.createFunction(" + m("h") + ", " + m("f") + ", " + m("f") + ")"); } },

    // r: regexp
    // The separate regex code is better at matching strings with regexps, but this is better at reusing the objects.
    // See https://bugzilla.mozilla.org/show_bug.cgi?id=808245 for why it is important to reuse regexp objects.
    { w: 1,  fun: function(d, b) { return assign(d, b, "r", makeRegex(d, b)); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "a", m("r") + ".exec(" + m("s") + ")"); } },
    { w: 3,  fun: function(d, b) { return makeRegexUseBlock(d, b, m("r")); } },
    { w: 3,  fun: function(d, b) { return makeRegexUseBlock(d, b, m("r"), m("s")); } },
    { w: 3,  fun: function(d, b) { return assign(d, b, "v", m("r") + "." + Random.index(builtinObjects["RegExp.prototype"])); } },

    // g: global or sandbox
    { w: 1,  fun: function(d, b) { return assign(d, b, "g", makeGlobal(d, b)); } },
    { w: 5,  fun: function(d, b) { return assign(d, b, "v", m("g") + ".eval(" + strToEval(d, b) + ")"); } },
    { w: 5,  fun: function(d, b) { return assign(d, b, "v", "evalcx(" + strToEval(d, b) + ", " + m("g") + ")"); } },
    { w: 5,  fun: function(d, b) { return assign(d, b, "v", "evaluate(" + strToEval(d, b) + ", { global: " + m("g") + ", fileName: " + Random.index(["'evaluate.js'", "null"]) + ", lineNumber: 42, newContext: " + makeBoolean(d, b) + ", compileAndGo: " + makeBoolean(d, b) + ", noScriptRval: " + makeBoolean(d, b) + ", catchTermination: " + makeBoolean(d, b) + ", saveFrameChain: " + ("bug 881999" && rnd(10000) ? "false" : makeBoolean(d, b)) + " })"); } },
    { w: 3,  fun: function(d, b) { return "schedulegc(" + m("g") + ");"; } },

    // Mix builtins between globals
    { w: 3,  fun: function(d, b) { return "/*MXX1*/" + assign(d, b, "o", m("g") + "." + Random.index(builtinProperties)); } },
    { w: 3,  fun: function(d, b) { return "/*MXX2*/" + m("g") + "." + Random.index(builtinProperties) + " = " + m() + ";"; } },
    { w: 3,  fun: function(d, b) { var prop = Random.index(builtinProperties); return "/*MXX3*/" + m("g") + "." + prop + " = " + m("g") + "." + prop + ";"; } },

    // f: function (?)
    // Could probably do better with args / b
    { w: 1,  fun: function(d, b) { return assign(d, b, "f", makeEvilCallback(d, b)); } },
    { w: 1,  fun: fdecl },
    { w: 2,  fun: function(d, b) { return m("f") + "(" + m() + ");"; } },

    // i: Iterator
    { w: 1,  fun: function(d, b) { return assign(d, b, "i", "new Iterator(" + m() + ")"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "i", "new Iterator(" + m() + ", true)"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "i", m("ema") + "." + Random.index(["entries", "keys", "values", "iterator"])); } },
    { w: 3,  fun: function(d, b) { return m("i") + ".next();"; } },
    { w: 3,  fun: function(d, b) { return m("i") + ".send(" + m() + ");"; } },
    // Other ways to build iterators: https://developer.mozilla.org/en/JavaScript/Guide/Iterators_and_Generators

    // v: Primitive
    { w: 2,  fun: function(d, b) { return assign(d, b, "v", Random.index(["4", "4.2", "NaN", "0", "-0", "Infinity", "-Infinity"])); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "v", "new Number(" + Random.index(["4", "4.2", "NaN", "0", "-0", "Infinity", "-Infinity"]) + ")"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "v", "new Number(" + m() + ")"); } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "v", makeBoolean(d, b)); } },
    { w: 2,  fun: function(d, b) { return assign(d, b, "v", Random.index(["undefined", "null", "true", "false"])); } },

    // evil things we can do to any object property
    { w: 1,  fun: function(d, b) { return "Object.defineProperty(" + m() + ", " + makePropertyName(d, b) + ", " + makePropertyDescriptor(d, b) + ");"; } },
    { w: 1,  fun: function(d, b) { return "/*ODP*/Object.defineProperty(" + m("") + ", " + makePropertyName(d, b) + ", { " + propertyDescriptorPrefix(d, b) + "get: " + makeEvilCallback(d,b) + ", set: " + makeEvilCallback(d, b) + " });"; } },
    { w: 1,  fun: function(d, b) { return "/*ODP*/Object.defineProperty(" + m("") + ", " + makePropertyName(d, b) + ", { " + propertyDescriptorPrefix(d, b) + "writable: " + makeBoolean(d,b) + ", value: " + val(d, b) + " });"; } },
    { w: 1,  fun: function(d, b) { return "Object.prototype.watch.call(" + m() + ", " + makePropertyName(d, b) + ", " + makeEvilCallback(d, b) + ");"; } },
    { w: 1,  fun: function(d, b) { return "Object.prototype.unwatch.call(" + m() + ", " + makePropertyName(d, b) + ");"; } },
    { w: 1,  fun: function(d, b) { return "delete " + m() + "[" + makePropertyName(d, b) + "];"; } },
    { w: 1,  fun: function(d, b) { return assign(d, b, "v", m() + "[" + makePropertyName(d, b) + "]"); } },
    { w: 1,  fun: function(d, b) { return m() + "[" + makePropertyName(d, b) + "] = " + val(d, b) + ";"; } },

    // evil things we can do to any object
    { w: 5,  fun: function(d, b) { return "print(" + m() + ");"; } },
    { w: 5,  fun: function(d, b) { return "print(uneval(" + m() + "));"; } },
    { w: 5,  fun: function(d, b) { return m() + ".toString = " + makeEvilCallback(d, b) + ";"; } },
    { w: 5,  fun: function(d, b) { return m() + ".toSource = " + makeEvilCallback(d, b) + ";"; } },
    { w: 5,  fun: function(d, b) { return m() + ".valueOf = " + makeEvilCallback(d, b) + ";"; } },
    { w: 2,  fun: function(d, b) { return m() + ".__iterator__ = " + makeEvilCallback(d, b) + ";"; } },
    { w: 1,  fun: function(d, b) { return m() + " = " + m() + ";"; } },
    { w: 1,  fun: function(d, b) { return m() + " = " + m("g") + ".objectEmulatingUndefined();"; } },
    { w: 1,  fun: function(d, b) { return m() + " = wrap(" + val(d, b) + ");"; } },
    { w: 1,  fun: function(d, b) { return m() + " = wrapWithProto(" + val(d, b) + ", " + val(d, b) + ");"; } },
    { w: 1,  fun: function(d, b) { return m("o") + " = " + m() + ".__proto__;"; } },
    { w: 5,  fun: function(d, b) { return m() + ".__proto__ = " + m() + ";"; } },
    { w: 10, fun: function(d, b) { return "for (var p in " + m() + ") { " + makeBuilderStatement(d - 1, b) + " " + makeBuilderStatement(d - 1, b) + " }"; } },
    { w: 10, fun: function(d, b) { return "for (var v of " + m() + ") { " + makeBuilderStatement(d - 1, b) + " " + makeBuilderStatement(d - 1, b) + " }"; } },
    { w: 10, fun: function(d, b) { return m() + " + " + m() + ";"; } }, // valueOf
    { w: 10, fun: function(d, b) { return m() + " + '';"; } }, // toString
    { w: 10, fun: function(d, b) { return m("v") + " = (" + m() + " instanceof " + m() + ");"; } },
    { w: 10, fun: function(d, b) { return m("v") + " = Object.prototype.isPrototypeOf.call(" + m() + ", " + m() + ");"; } },
    { w: 2,  fun: function(d, b) { return "Object." + Random.index(["preventExtensions", "seal", "freeze"]) + "(" + m() + ");"; } },

    // Be promiscuous with the rest of jsfunfuzz
    { w: 1,  fun: function(d, b) { return m() + " = x;"; } },
    { w: 1,  fun: function(d, b) { return "x = " + m() + ";"; } },
    { w: 5,  fun: makeStatement },

    { w: 5,  fun: initializeEverything },
  ]);
  makeBuilderStatement = function(d, b) {
    return (Random.index(builderStatementMakers))(d - 1, b);
  };
})();


function makeParallelArraySizeAndInitializer(d, b)
{
  if (rnd(TOTALLY_RANDOM) == 2) return totallyRandom(d, b);

  var dimensions = rnd(5) ? 1 : 2;
  var sizes = [];
  var argList = [];
  for (var i = 0; i < dimensions; ++i) {
    sizes[i] = (rnd(100) === 0) ? makeExpr(d, b) :
      (dimensions == 1) ? rnd(20000) + 1 :
      rnd(120) + 1;

    argList.push("x" + i);
  }
  var bv = b.concat(argList);

  var sizeArg = (dimensions == 1 && rnd(2)) ? sizes[0] : "[" + sizes.join(", ") + "]";

  var elementalFunctionArg = rnd(2) ?
    makeFunction(d, bv) :
    "function(" + argList.join(", ") + ") { " + parallelBail(d, bv, argList) + "return " + (rnd(2) ? argList[0] : makeExpr(d, bv)) + "; }";

  return sizeArg + ", " + elementalFunctionArg;
}

function makeParallelMap(d, b)
{
  // Map can also see indices and the array, but we don't use them here
  var bv = b.concat(["e"]);
  return "function(e) { " + parallelBail(d, bv, ["e"]) + "return " + (rnd(2) ? "e" : makeExpr(d, bv)) + "; }";
}

function makeParallelFilter(d, b)
{
  var bv = b.concat(["e", "i", "s"]);
  return "function(e, i, s) { " + parallelBail(d, bv, ["e", "i"]) + "return " + (rnd(2) ? "i%2" : makeExpr(d, bv)) + "; }";
}

function makeParallelBinary(d, b)
{
  var bv = b.concat(["a", "b"]);
  return "function(a, b) { " + parallelBail(d, bv, ["a", "b"]) + "return " + (rnd(2) ? "a-b" : makeExpr(d, bv)) + "; }";
}

function parallelBail(d, b, inputs)
{
  if (rnd(3))
    return "";

  var condition = infrequentCondition(Random.index(inputs), 2000);
  return "if (" + condition + ") { " + makeStatement(d, b) + "return " + makeExpr(d, b) + " }";
}

function infrequentCondition(v, n)
{
  switch (rnd(20)) {
    case 0: return true;
    case 1: return false;
    case 2: return v + " > " + rnd(n);
    default: var mod = rnd(n) + 2; var target = rnd(mod); return "/*ICCD*/" + v + " % " + mod + (rnd(8) ? " == " : " != ") + target;
  }
}

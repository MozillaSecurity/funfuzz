
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

/* global builtinFunctions, builtinObjects, builtinProperties, loopCount, makeAsmJSFunction, makeAsmJSModule */
/* global makeBoolean, makeExpr, makeFunction, makeFunctionBody, makeFunOnCallChain, makeGlobal, makeIterable */
/* global makePropertyDescriptor, makePropertyName, makeRegex, makeRegexUseBlock, makeRegisterStompFunction */
/* global makeScriptForEval, makeStatement, Random, rnd, simpleSource, typedArrayConstructors, uniqueVarName */
/* global varBinder */

/* ******************* *
 * TEST BUILT-IN TYPES *
 * ******************* */

var makeBuilderStatement;
var makeEvilCallback;

(function setUpBuilderStuff () {
  var ARRAY_SIZE = 20;
  var OBJECTS_PER_TYPE = 3;
  var smallPowersOfTwo = [1, 2, 4, 8]; // The largest typed array views are 64-bit aka 8-byte
  function bufsize () { return rnd(ARRAY_SIZE) * Random.index(smallPowersOfTwo); } /* eslint-disable-line require-jsdoc */
  function arrayIndex (d, b) { /* eslint-disable-line require-jsdoc */
    switch (rnd(8)) {
      /* eslint-disable no-multi-spaces */
      case 0:  return m("v");
      case 1:  return makeExpr(d - 1, b);
      case 2:  return `({valueOf: function() { ${makeStatement(d, b)}return ${rnd(ARRAY_SIZE)}; }})`;
      default: return `${rnd(ARRAY_SIZE)}`;
      /* eslint-enable no-multi-spaces */
    }
  }

  // Emit a variable name for type-abbreviation t.
  function m (t) { /* eslint-disable-line require-jsdoc */
    if (!t) { t = "aosmevbtihgfp"; }
    t = t.charAt(rnd(t.length));
    var name = t + rnd(OBJECTS_PER_TYPE);
    switch (rnd(24)) {
      /* eslint-disable no-multi-spaces */
      case 0:  return m("o");
      case 1:  return `${m("o")}.${name}`;
      case 2:  return m("g");
      case 3:  return `${m("g")}.${name}`;
      case 4:  return `this.${name}`;
      default: return name;
      /* eslint-enable no-multi-spaces */
    }
  }

  function val (d, b) { /* eslint-disable-line require-jsdoc */
    if (rnd(10)) { return m(); }
    return makeExpr(d, b);
  }

  // Emit an assignment (or a roughly-equivalent getter)
  function assign (d, b, t, rhs) { /* eslint-disable-line require-jsdoc */
    switch (rnd(18)) {
      // Could have two forms of the getter: one that computes it each time on demand,
      // and one that computes a constant-function closure
      /* eslint-disable no-multi-spaces */
      case 0:  return (
        "Object.defineProperty(" +
        `${rnd(8) ? "this" : m("og")}, ` +
        `${simpleSource(m(t))}, ` +
        `{ ${propertyDescriptorPrefix(d - 1, b)} get: function() { ${rnd(8) ? "" : makeBuilderStatement(d - 1, b)} return ${rhs}; } }` +
      ");"
      );
      case 1:  return `${Random.index(varBinder) + m(t)} = ${rhs};`;
      default: return `${m(t)} = ${rhs};`;
      /* eslint-enable no-multi-spaces */
    }
  }

  function makeCounterClosure (d, b) { /* eslint-disable-line require-jsdoc */
    // A closure with a counter. Do stuff depending on the counter.
    var v = uniqueVarName();
    var infrequently = infrequentCondition(v, 10);
    return (
      "(function mcc_() { " +
        `var ${v} = 0; ` +
        "return function() { " +
          `++${v}; ` +
            (rnd(3) ?
              `if (${infrequently}) { dumpln('hit!'); ${makeBuilderStatements(d, b)} } ` +
              `else { dumpln('miss!'); ${makeBuilderStatements(d, b)} } ` :
              `${m("f")}(${infrequently});`
            ) +
        "};" +
      "})()");
  }

  function fdecl (d, b) { /* eslint-disable-line require-jsdoc */
    var argName = m();
    var bv = b.concat([argName]);
    return `function ${m("f")}(${argName}) ${makeFunctionBody(d, bv)}`;
  }

  function makeBuilderStatements (d, b) { /* eslint-disable-line require-jsdoc */
    var s = "";
    var extras = rnd(4);
    for (var i = 0; i < extras; ++i) {
      s += `try { ${makeBuilderStatement(d - 2, b)} } catch(e${i}) { } `;
    }
    s += makeBuilderStatement(d - 1, b);
    return s;
  }

  var builderFunctionMakers = Random.weighted([
    { w: 9, v: function (d, b) { return `(function() { ${makeBuilderStatements(d, b)} return ${m()}; })`; } },
    { w: 1, v: function (d, b) { return `(function() { ${makeBuilderStatements(d, b)} throw ${m()}; })`; } },
    { w: 1, v: function (d, b) { return `(function(j) { ${m("f")}(j); })`; } }, // a function that just makes one call is begging to be inlined
    // The following pair create and use boolean-using functions.
    { w: 4, v: function (d, b) { return `(function(j) { if (j) { ${makeBuilderStatements(d, b)} } else { ${makeBuilderStatements(d, b)} } })`; } },
    { w: 4, v: function (d, b) { return `(function() { for (var j=0;j<${loopCount()};++j) { ${m("f")}(j%${2 + rnd(4)}==${rnd(2)}); } })`; } },
    { w: 1, v: function (d, b) { return `${Random.index(builtinFunctions)}.bind(${m()})`; } },
    { w: 5, v: function (d, b) { return m("f"); } },
    { w: 3, v: makeCounterClosure },
    { w: 2, v: makeFunction },
    { w: 1, v: makeAsmJSModule },
    { w: 1, v: makeAsmJSFunction },
    { w: 1, v: makeRegisterStompFunction }
  ]);
  makeEvilCallback = function (d, b) {
    return (Random.index(builderFunctionMakers))(d - 1, b);
  };

  var handlerTraps = ["getOwnPropertyDescriptor", "defineProperty", "ownKeys", "deleteProperty", "has", "get", "set",
    "getPrototypeOf", "setPrototypeOf", "isExtensible", "preventExtensions", "apply", "construct"];

  function forwardingHandler (d, b) { /* eslint-disable-line require-jsdoc */
    return (
      "({" +
        "getOwnPropertyDescriptor: function(target, name) { Z; var desc = Reflect.getOwnPropertyDescriptor(X); desc.configurable = true; return desc; }, " +
        "defineProperty: function(target, name, desc) { Z; return Reflect.defineProperty(X, name, desc); }, " +
        "ownKeys: function(target) { Z; return Reflect.ownKeys(X); }, " +
        "deleteProperty: function(target, name) { Z; return Reflect.deleteProperty(X, name); }, " +
        "has: function(target, name) { Z; return name in X; }, " +
        "get: function(target, name, receiver) { Z; return Reflect.get(X, name, receiver); }, " +
        "set: function(target, name, val, receiver) { Z; return Reflect.set(X, name, val, receiver); }, " +
        "getPrototypeOf: function(target) { Z; return Reflect.getPrototypeOf(X); }" +
        "setPrototypeOf: function(target, proto) { Z; return Reflect.setPrototypeOf(X, proto); }" +
        "isExtensible: function(target) { Z; return Reflect.isExtensible(X); }" +
        "preventExtensions: function(target) { Z; return Reflect.preventExtensions(X); }" +
        "apply: function(target, thisArgument, argumentsList) { Z; return Reflect.apply(X, thisArgument, argumentsList); }" +
        "construct: function(target, argumentsList, newTarget) { Z; return Reflect.construct(X, argumentsList, newTarget); }" +
      "})"
    )
      .replace(/X/g, m())
      .replace(/Z/g, function () {
        switch (rnd(20)) {
          /* eslint-disable no-multi-spaces */
          case 0:  return `return ${m()}`;
          case 1:  return `throw ${m()}`;
          default: return makeBuilderStatement(d - 2, b);
          /* eslint-enable no-multi-spaces */
        }
      });
  }

  function propertyDescriptorPrefix (d, b) { /* eslint-disable-line require-jsdoc */
    return `configurable: ${makeBoolean(d, b)}, enumerable: ${makeBoolean(d, b)}, `;
  }

  function strToEval (d, b) { /* eslint-disable-line require-jsdoc */
    switch (rnd(5)) {
      /* eslint-disable no-multi-spaces */
      case 0:  return simpleSource(fdecl(d, b));
      case 1:  return simpleSource(makeBuilderStatement(d, b));
      default: return simpleSource(makeScriptForEval(d, b));
      /* eslint-enable no-multi-spaces */
    }
  }

  function evaluateFlags (d, b) { /* eslint-disable-line require-jsdoc */
    // Options are in js.cpp: Evaluate() and ParseCompileOptions()
    return (`({ global: ${m("g")}` +
      `, fileName: ${Random.index(["'evaluate.js'", "null"])}` +
      ", lineNumber: 42" +
      `, isRunOnce: ${makeBoolean(d, b)}` +
      `, noScriptRval: ${makeBoolean(d, b)}` +
      `, saveIncrementalBytecode: ${makeBoolean(d, b)}` +
      `, sourceIsLazy: ${makeBoolean(d, b)}` +
      `, catchTermination: ${makeBoolean(d, b)}` +
      ((rnd(5) === 0) ? (
        ((rnd(2) === 0) ? `, element: ${m("o")}` : "") +
        ((rnd(2) === 0) ? `, elementAttributeName: ${m("s")}` : "") +
        ((rnd(2) === 0) ? `, sourceMapURL: ${m("s")}` : "")
      ) : ""
      ) +
    " })");
  }

  var initializedEverything = false;
  function initializeEverything (d, b) { /* eslint-disable-line require-jsdoc */
    if (initializedEverything) { return ";"; }
    initializedEverything = true;

    var s = "";
    for (var i = 0; i < OBJECTS_PER_TYPE; ++i) {
      s += `a${i} = []; `;
      s += `o${i} = {}; `;
      s += `s${i} = ''; `;
      s += `r${i} = /x/; `;
      s += `g${i} = ${makeGlobal(d, b)}; `;
      s += `f${i} = function(){}; `;
      s += `m${i} = new WeakMap; `;
      s += `e${i} = new Set; `;
      s += `v${i} = null; `;
      s += `b${i} = new ArrayBuffer(64); `;
      s += `t${i} = new Uint8ClampedArray; `;
      // nothing for iterators, handlers
    }
    return s;
  }

  // Emit a method call expression, in one of the following forms:
  //   Array.prototype.push.apply(a1, [x])
  //   Array.prototype.push.call(a1, x)
  //   a1.push(x)
  function method (d, b, clazz, obj, meth, arglist) { /* eslint-disable-line require-jsdoc */
    // Sometimes ignore our arguments
    if (rnd(10) === 0) { arglist = []; }

    // Stuff in extra arguments
    while (rnd(2)) { arglist.push(val(d, b)); }

    // Emit a method call expression
    switch (rnd(4)) {
      /* eslint-disable no-multi-spaces */
      case 0:  return `${clazz}.prototype.${meth}.apply(${obj}, [${arglist.join(", ")}])`;
      case 1:  return `${clazz}.prototype.${meth}.call(${[obj].concat(arglist).join(", ")})`;
      default: return `${obj}.${meth}(${arglist.join(", ")})`;
      /* eslint-enable no-multi-spaces */
    }
  }

  function severalargs (f) { /* eslint-disable-line require-jsdoc */
    var arglist = [];
    arglist.push(f());
    while (rnd(2)) {
      arglist.push(f());
    }
    return arglist;
  }

  var builderStatementMakers = Random.weighted([
    // a: Array
    { w: 1, v: function (d, b) { return assign(d, b, "a", "[]"); } },
    { w: 1, v: function (d, b) { return assign(d, b, "a", "new Array"); } },
    { w: 1, v: function (d, b) { return assign(d, b, "a", makeIterable(d, b)); } },
    { w: 1, v: function (d, b) { return `${m("a")}.length = ${arrayIndex(d, b)};`; } },
    { w: 8, v: function (d, b) { return assign(d, b, "v", `${m("at")}.length`); } },
    { w: 4, v: function (d, b) { return `${m("at")}[${arrayIndex(d, b)}] = ${val(d, b)};`; } },
    { w: 4, v: function (d, b) { return `${val(d, b)} = ${m("at")}[${arrayIndex(d, b)}];`; } },
    { w: 1, v: function (d, b) { return assign(d, b, "a", `${makeFunOnCallChain(d, b)}.arguments`); } }, // a read-only arguments object
    { w: 1, v: function (d, b) { return assign(d, b, "a", "arguments"); } }, // a read-write arguments object

    // Array indexing
    { w: 3, v: function (d, b) { return `${m("at")}[${arrayIndex(d, b)}];`; } },
    { w: 3, v: function (d, b) { return `${m("at")}[${arrayIndex(d, b)}] = ${makeExpr(d, b)};`; } },
    { w: 1, v: function (d, b) { return `/*ADP-1*/Object.defineProperty(${m("a")}, ${arrayIndex(d, b)}, ${makePropertyDescriptor(d, b)});`; } },
    { w: 1, v: function (d, b) { return `/*ADP-2*/Object.defineProperty(${m("a")}, ${arrayIndex(d, b)}, { ${propertyDescriptorPrefix(d, b)}get: ${makeEvilCallback(d, b)}, set: ${makeEvilCallback(d, b)} });`; } },
    { w: 1, v: function (d, b) { return `/*ADP-3*/Object.defineProperty(${m("a")}, ${arrayIndex(d, b)}, { ${propertyDescriptorPrefix(d, b)}writable: ${makeBoolean(d, b)}, value: ${val(d, b)} });`; } },

    // Array mutators
    { w: 5, v: function (d, b) { return `${method(d, b, "Array", m("a"), "push", severalargs(function () { return val(d, b); }))};`; } },
    { w: 5, v: function (d, b) { return `${method(d, b, "Array", m("a"), "pop", [])};`; } },
    { w: 5, v: function (d, b) { return `${method(d, b, "Array", m("a"), "unshift", severalargs(function () { return val(d, b); }))};`; } },
    { w: 5, v: function (d, b) { return `${method(d, b, "Array", m("a"), "shift", [])};`; } },
    { w: 5, v: function (d, b) { return `${method(d, b, "Array", m("a"), "reverse", [])};`; } },
    { w: 5, v: function (d, b) { return `${method(d, b, "Array", m("a"), "sort", [makeEvilCallback(d, b)])};`; } },
    { w: 5, v: function (d, b) { return `${method(d, b, "Array", m("a"), "splice", [arrayIndex(d, b) - arrayIndex(d, b), arrayIndex(d, b)])};`; } },
    // Array accessors
    { w: 1, v: function (d, b) { return assign(d, b, "s", method(d, b, "Array", m("a"), "join", [m("s")])); } },
    { w: 1, v: function (d, b) { return assign(d, b, "a", method(d, b, "Array", m("a"), "concat", severalargs(function () { return m("at"); }))); } },
    { w: 1, v: function (d, b) { return assign(d, b, "a", method(d, b, "Array", m("a"), "slice", [arrayIndex(d, b) - arrayIndex(d, b), arrayIndex(d, b) - arrayIndex(d, b)])); } },

    // Array iterators
    { w: 5, v: function (d, b) { return `${method(d, b, "Array", m("a"), "forEach", [makeEvilCallback(d, b)])};`; } },
    { w: 1, v: function (d, b) { return assign(d, b, "a", method(d, b, "Array", m("a"), "map", [makeEvilCallback(d, b)])); } },
    { w: 1, v: function (d, b) { return assign(d, b, "a", method(d, b, "Array", m("a"), "filter", [makeEvilCallback(d, b)])); } },
    { w: 1, v: function (d, b) { return assign(d, b, "v", method(d, b, "Array", m("a"), "some", [makeEvilCallback(d, b)])); } },
    { w: 1, v: function (d, b) { return assign(d, b, "v", method(d, b, "Array", m("a"), "every", [makeEvilCallback(d, b)])); } },

    // Array reduction, either with a starting value or with the default of starting with the first two elements.
    { w: 1, v: function (d, b) { return assign(d, b, "v", method(d, b, "Array", m("a"), Random.index(["reduce, reduceRight"]), [makeEvilCallback(d, b)])); } },
    { w: 1, v: function (d, b) { return assign(d, b, "v", method(d, b, "Array", m("a"), Random.index(["reduce, reduceRight"]), [makeEvilCallback(d, b), val(d, b)])); } },

    // Typed Objects (aka Binary Data)
    // http://wiki.ecmascript.org/doku.php?id=harmony:typed_objects (does not match what's in spidermonkey as of 2014-02-11)
    // Do I need to keep track of 'types', 'objects of those types', and 'arrays of objects of those types'?
    // { w: 1,  v: function(d, b) { return assign(d, b, "d", `${m("d")}.flatten()`); } },
    // { w: 1,  v: function(d, b) { return assign(d, b, "d", `${m("d")}.partition(${rnd(2) ? m("v") : rnd(10)})`); } },

    // o: Object
    { w: 1, v: function (d, b) { return assign(d, b, "o", "{}"); } },
    { w: 1, v: function (d, b) { return assign(d, b, "o", "new Object"); } },
    { w: 1, v: function (d, b) { return assign(d, b, "o", `Object.create(${val(d, b)})`); } },
    { w: 3, v: function (d, b) { return `selectforgc(${m("o")});`; } },

    // s: String
    { w: 1, v: function (d, b) { return assign(d, b, "s", "''"); } },
    { w: 1, v: function (d, b) { return assign(d, b, "s", "new String"); } },
    { w: 1, v: function (d, b) { return assign(d, b, "s", `new String(${m()})`); } },
    { w: 1, v: function (d, b) { return assign(d, b, "s", `${m("s")}.charAt(${arrayIndex(d, b)})`); } },
    { w: 5, v: function (d, b) { return `${m("s")} += 'x';`; } },
    { w: 5, v: function (d, b) { return `${m("s")} += ${m("s")};`; } },
    // Should add substr, substring, replace

    // m: Map, WeakMap
    { w: 1, v: function (d, b) { return assign(d, b, "m", "new Map"); } },
    { w: 1, v: function (d, b) { return assign(d, b, "m", `new Map(${m()})`); } },
    { w: 1, v: function (d, b) { return assign(d, b, "m", "new WeakMap"); } },
    { w: 5, v: function (d, b) { return `${m("m")}.has(${val(d, b)});`; } },
    { w: 4, v: function (d, b) { return `${m("m")}.get(${val(d, b)});`; } },
    { w: 1, v: function (d, b) { return assign(d, b, null, `${m("m")}.get(${val(d, b)})`); } },
    { w: 5, v: function (d, b) { return `${m("m")}.set(${val(d, b)}, ${val(d, b)});`; } },
    { w: 3, v: function (d, b) { return `${m("m")}.delete(${val(d, b)});`; } },

    // e: Set
    { w: 1, v: function (d, b) { return assign(d, b, "e", "new Set"); } },
    { w: 1, v: function (d, b) { return assign(d, b, "e", `new Set(${m()})`); } },
    { w: 5, v: function (d, b) { return `${m("e")}.has(${val(d, b)});`; } },
    { w: 5, v: function (d, b) { return `${m("e")}.add(${val(d, b)});`; } },
    { w: 3, v: function (d, b) { return `${m("e")}.delete(${val(d, b)});`; } },

    // b: Buffer
    { w: 1, v: function (d, b) { return assign(d, b, "b", `new ${arrayBufferType()}(${bufsize()})`); } },
    { w: 1, v: function (d, b) { return assign(d, b, "b", `${m("t")}.buffer`); } },
    { w: 1, v: function (d, b) { return `neuter(${m("b")}, ${rnd(2) ? '"same-data"' : '"change-data"'});`; } },

    // t: Typed arrays, aka ArrayBufferViews
    // Can be constructed using a length, typed array, sequence (e.g. array), or buffer with optional offsets!
    { w: 1, v: function (d, b) { return assign(d, b, "t", `new ${Random.index(typedArrayConstructors)}(${arrayIndex(d, b)})`); } },
    { w: 3, v: function (d, b) { return assign(d, b, "t", `new ${Random.index(typedArrayConstructors)}(${m("abt")})`); } },
    { w: 1, v: function (d, b) { return assign(d, b, "t", `new ${Random.index(typedArrayConstructors)}(${m("b")}, ${bufsize()}, ${arrayIndex(d, b)})`); } },
    { w: 1, v: function (d, b) { return assign(d, b, "t", `${m("t")}.subarray(${arrayIndex(d, b)})`); } },
    { w: 1, v: function (d, b) { return assign(d, b, "t", `${m("t")}.subarray(${arrayIndex(d, b)}, ${arrayIndex(d, b)})`); } },
    { w: 3, v: function (d, b) { return `${m("t")}.set(${m("at")}, ${arrayIndex(d, b)});`; } },
    { w: 1, v: function (d, b) { return assign(d, b, "v", `${m("tb")}.byteLength`); } },
    { w: 1, v: function (d, b) { return assign(d, b, "v", `${m("t")}.byteOffset`); } },
    { w: 1, v: function (d, b) { return assign(d, b, "v", `${m("t")}.BYTES_PER_ELEMENT`); } },

    // h: proxy handler
    { w: 1, v: function (d, b) { return assign(d, b, "h", "{}"); } },
    { w: 1, v: function (d, b) { return assign(d, b, "h", forwardingHandler(d, b)); } },
    { w: 1, v: function (d, b) { return `delete ${m("h")}.${Random.index(handlerTraps)};`; } },
    { w: 4, v: function (d, b) { return `${m("h")}.${Random.index(handlerTraps)} = ${makeEvilCallback(d, b)};`; } },
    { w: 4, v: function (d, b) { return `${m("h")}.${Random.index(handlerTraps)} = ${m("f")};`; } },
    { w: 1, v: function (d, b) { return assign(d, b, null, `new Proxy(${m()}, ${m("h")})`); } },
    { w: 1, v: function (d, b) { return assign(d, b, "f", `new Proxy(${m("f")}, ${m("h")})`); } },

    // r: regexp
    // The separate regex code is better at matching strings with regexps, but this is better at reusing the objects.
    // See https://bugzilla.mozilla.org/show_bug.cgi?id=808245 for why it is important to reuse regexp objects.
    { w: 1, v: function (d, b) { return assign(d, b, "r", makeRegex(d, b)); } },
    { w: 1, v: function (d, b) { return assign(d, b, "a", `${m("r")}.exec(${m("s")})`); } },
    { w: 3, v: function (d, b) { return makeRegexUseBlock(d, b, m("r")); } },
    { w: 3, v: function (d, b) { return makeRegexUseBlock(d, b, m("r"), m("s")); } },
    { w: 3, v: function (d, b) { return assign(d, b, "v", `${m("r")}.${Random.index(builtinObjects["RegExp.prototype"])}`); } },

    // g: global or sandbox
    { w: 1, v: function (d, b) { return assign(d, b, "g", makeGlobal(d, b)); } },
    { w: 5, v: function (d, b) { return assign(d, b, "v", `${m("g")}.eval(${strToEval(d, b)})`); } },
    { w: 5, v: function (d, b) { return assign(d, b, "v", `evalcx(${strToEval(d, b)}, ${m("g")})`); } },
    { w: 5, v: function (d, b) { return assign(d, b, "v", `evaluate(${strToEval(d, b)}, ${evaluateFlags(d, b)})`); } },
    { w: 2, v: function (d, b) { return `${m("g")}.offThreadCompileScript(${strToEval(d, b)});`; } },
    { w: 3, v: function (d, b) { return `${m("g")}.offThreadCompileScript(${strToEval(d, b)}, ${evaluateFlags(d, b)});`; } },
    { w: 5, v: function (d, b) { return assign(d, b, "v", `${m("g")}.runOffThreadScript()`); } },
    { w: 3, v: function (d, b) { return `(void schedulegc(${m("g")}));`; } },

    // Mix builtins between globals
    { w: 3, v: function (d, b) { return `/*MXX1*/${assign(d, b, "o", m("g") + "." + Random.index(builtinProperties))}`; } },
    { w: 3, v: function (d, b) { return `/*MXX2*/${m("g")}.${Random.index(builtinProperties)} = ${m()};`; } },
    { w: 3, v: function (d, b) { var prop = Random.index(builtinProperties); return `/*MXX3*/${m("g")}.${prop} = ${m("g")}.${prop};`; } },

    // f: function (?)
    // Could probably do better with args / b
    { w: 1, v: function (d, b) { return assign(d, b, "f", makeEvilCallback(d, b)); } },
    { w: 1, v: fdecl },
    { w: 2, v: function (d, b) { return `${m("f")}(${m()});`; } },

    // v: Primitive
    { w: 2, v: function (d, b) { return assign(d, b, "v", Random.index(["4", "4.2", "NaN", "0", "-0", "Infinity", "-Infinity"])); } },
    { w: 1, v: function (d, b) { return assign(d, b, "v", `new Number(${Random.index(["4", "4.2", "NaN", "0", "-0", "Infinity", "-Infinity"])})`); } },
    { w: 1, v: function (d, b) { return assign(d, b, "v", `new Number(${m()})`); } },
    { w: 1, v: function (d, b) { return assign(d, b, "v", makeBoolean(d, b)); } },
    { w: 2, v: function (d, b) { return assign(d, b, "v", Random.index(["undefined", "null", "true", "false"])); } },

    // evil things we can do to any object property
    { w: 1, v: function (d, b) { return `/*ODP-1*/Object.defineProperty(${m()}, ${makePropertyName(d, b)}, ${makePropertyDescriptor(d, b)});`; } },
    { w: 1, v: function (d, b) { return `/*ODP-2*/Object.defineProperty(${m()}, ${makePropertyName(d, b)}, { ${propertyDescriptorPrefix(d, b)}get: ${makeEvilCallback(d, b)}, set: ${makeEvilCallback(d, b)} });`; } },
    { w: 1, v: function (d, b) { return `/*ODP-3*/Object.defineProperty(${m()}, ${makePropertyName(d, b)}, { ${propertyDescriptorPrefix(d, b)}writable: ${makeBoolean(d, b)}, value: ${val(d, b)} });`; } },
    { w: 1, v: function (d, b) { return `delete ${m()}[${makePropertyName(d, b)}];`; } },
    { w: 1, v: function (d, b) { return assign(d, b, "v", `${m()}[${makePropertyName(d, b)}]`); } },
    { w: 1, v: function (d, b) { return `${m()}[${makePropertyName(d, b)}] = ${val(d, b)};`; } },

    // evil things we can do to any object
    { w: 5, v: function (d, b) { return `print(${m()});`; } },
    { w: 5, v: function (d, b) { return `print(uneval(${m()}));`; } },
    { w: 5, v: function (d, b) { return `${m()}.toString = ${makeEvilCallback(d, b)};`; } },
    { w: 5, v: function (d, b) { return `${m()}.valueOf = ${makeEvilCallback(d, b)};`; } },
    { w: 1, v: function (d, b) { return `${m()} = ${m()};`; } },
    { w: 1, v: function (d, b) { return `${m()} = ${m("g")}.createIsHTMLDDA();`; } },
    { w: 10, v: function (d, b) { return `${m("o")} = ${m()}.__proto__;`; } },
    { w: 20, v: function (d, b) { return `${m()}.__proto__ = {};`; } },
    { w: 20, v: function (d, b) { return `${m()}.__proto__ = ${m()};`; } },
    { w: 10, v: function (d, b) { return `for (var p in ${m()}) { ${makeBuilderStatements(d, b)} }`; } },
    { w: 10, v: function (d, b) { return `for (var v of ${m()}) { ${makeBuilderStatements(d, b)} }`; } },
    { w: 10, v: function (d, b) { return `${m()} + ${m()};`; } }, // valueOf
    { w: 10, v: function (d, b) { return `${m()} + '';`; } }, // toString
    { w: 10, v: function (d, b) { return `${m("v")} = (${m()} instanceof ${m()});`; } },
    { w: 10, v: function (d, b) { return `${m("v")} = Object.prototype.isPrototypeOf.call(${m()}, ${m()});`; } },
    { w: 2, v: function (d, b) { return `Object.${Random.index(["preventExtensions", "seal", "freeze"])}(${m()});`; } },

    // Be promiscuous with the rest of jsfunfuzz
    { w: 1, v: function (d, b) { return `${m()} = x;`; } },
    { w: 1, v: function (d, b) { return `x = ${m()};`; } },
    { w: 5, v: makeStatement },

    // Stick in empty for-loops
    { w: 5, v: function (d, b) { return "for (let i = 0; i < 999; i++) {}"; } },

    { w: 5, v: initializeEverything }
  ]);
  makeBuilderStatement = function (d, b) {
    return (Random.index(builderStatementMakers))(d - 1, b);
  };
})();

function infrequentCondition (v, n) { /* eslint-disable-line require-jsdoc */
  switch (rnd(20)) {
    case 0: return true;
    case 1: return false;
    case 2: return `${v} > ${rnd(n)}`;
    default: var mod = rnd(n) + 2; var target = rnd(mod); return `/*ICCD*/${v} % ${mod}${rnd(8) ? " == " : " != "}${target}`;
  }
}

var arrayBufferType = "SharedArrayBuffer" in this ?
  function () { return rnd(2) ? "SharedArrayBuffer" : "ArrayBuffer"; } :
  function () { return "ArrayBuffer"; };

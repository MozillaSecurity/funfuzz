
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

/* exported makeProxyHandler */
/* global bp:writable, makeExpr, makeFunction, Random, rnd, TOTALLY_RANDOM, totallyRandom */

// In addition, can always use "undefined" or makeFunction
// Forwarding proxy code based on http://wiki.ecmascript.org/doku.php?id=harmony:proxies "Example: a no-op forwarding proxy"
// The letter 'x' is special.
var proxyHandlerProperties = {
  getOwnPropertyDescriptor: {
    empty: "function(target, name) {}",
    forward: "function(target, name) { var desc = Reflect.getOwnPropertyDescriptor(x); desc.configurable = true; return desc; }",
    throwing: "function(target, name) { return {get: function() { throw 4; }, set: function() { throw 5; }}; }"
  },
  defineProperty: {
    empty: "function(target, name, desc) {}",
    forward: "function(target, name, desc) { return Reflect.defineProperty(x, name, desc); }"
  },
  ownKeys: {
    empty: "function(target) { return []; }",
    forward: "function(target) { return Reflect.ownKeys(x); }"
  },
  deleteProperty: {
    empty: "function(target, name) { return true; }",
    yes: "function(target, name) { return true; }",
    no: "function(target, name) { return false; }",
    forward: "function(target, name) { return Reflect.deleteProperty(x, name); }"
  },
  has: {
    empty: "function(target, name) { return false; }",
    yes: "function(target, name) { return true; }",
    no: "function(target, name) { return false; }",
    forward: "function(target, name) { return name in x; }"
  },
  get: {
    empty: "function(target, name, receiver) { return undefined }",
    forward: "function(target, name, receiver) { return Reflect.get(x, name, receiver); }",
    bind: "function(target, name, receiver) { var prop = Reflect.get(x, name, receiver); return (typeof prop) === 'function' ? prop.bind(x) : prop; }"
  },
  set: {
    empty: "function(target, name, val, receiver) { return true; }",
    yes: "function(target, name, val, receiver) { return true; }",
    no: "function(target, name, val, receiver) { return false; }",
    forward: "function(target, name, val, receiver) { return Reflect.set(x, name, val, receiver); }"
  },
  getPrototypeOf: {
    empty: "function(target) { return null; }",
    forward: "function(target) { return Reflect.getPrototypeOf(x); }"
  },
  setPrototypeOf: {
    yes: "function(target, proto) { return true; }",
    no: "function(target, proto) { return false; }",
    forward: "function(target, proto) { return Reflect.setPrototypeOf(x, proto); }"
  },
  isExtensible: {
    yes: "function(target) { return true; }",
    no: "function(target) { return false; }",
    forward: "function(target) { return Reflect.isExtensible(x); }"
  },
  preventExtensions: {
    yes: "function(target) { return true; }",
    no: "function(target) { return false; }",
    forward: "function(target) { return Reflect.preventExtensions(x); }"
  },
  apply: {
    empty: "function(target, thisArgument, argumentsList) {}",
    forward: "function(target, thisArgument, argumentsList) { return Reflect.apply(x, thisArgument, argumentsList); }"
  },
  construct: {
    empty: "function(target, argumentsList, newTarget) { return []; }",
    invalid: "function(target, argumentsList, newTarget) { return 3; }",
    forward: "function(target, argumentsList, newTarget) { return Reflect.construct(x, argumentsList, newTarget); }"
  }
};

function makeProxyHandlerFactory (d, b) { /* eslint-disable-line require-jsdoc */
  if (rnd(TOTALLY_RANDOM) === 2) return totallyRandom(d, b);

  if (d < 1) { return "({/*TOODEEP*/})"; }

  try { // in case we screwed Object.prototype, breaking proxyHandlerProperties
    var preferred = Random.index(["empty", "forward", "yes", "no", "bind", "throwing"]);
    var fallback = Random.index(["empty", "forward"]);
    var fidelity = rnd(10);

    var handlerFactoryText = "(function handlerFactory(x) {";
    handlerFactoryText += "return {";

    if (rnd(2)) {
      // handlerFactory has an argument 'x'
      bp = b.concat(["x"]);
    } else {
      // handlerFactory has no argument
      handlerFactoryText = handlerFactoryText.replace(/x/, "");
      bp = b;
    }

    for (var p in proxyHandlerProperties) {
      var funText;
      if (proxyHandlerProperties[p][preferred] && rnd(10) <= fidelity) {
        funText = proxyMunge(proxyHandlerProperties[p][preferred], p);
      } else {
        switch (rnd(7)) {
          /* eslint-disable no-multi-spaces */
          case 0:  funText = makeFunction(d - 3, bp); break;
          case 1:  funText = "undefined"; break;
          case 2:  funText = "function() { throw 3; }"; break;
          default: funText = proxyMunge(proxyHandlerProperties[p][fallback], p);
          /* eslint-enable no-multi-spaces */
        }
      }
      handlerFactoryText += `${p}: ${funText}, `;
    }

    handlerFactoryText += "}; })";

    return handlerFactoryText;
  } catch (e) {
    return "({/* :( */})";
  }
}

function proxyMunge (funText, p) { /* eslint-disable-line require-jsdoc */
  // funText = funText.replace(/\{/, `{ var yum = 'PCAL'; dumpln(yum + 'LED: ${p}');`);
  return funText;
}

function makeProxyHandler (d, b) { /* eslint-disable-line require-jsdoc */
  if (rnd(TOTALLY_RANDOM) === 2) return totallyRandom(d, b);

  return `${makeProxyHandlerFactory(d, b)}(${makeExpr(d - 3, b)})`;
}

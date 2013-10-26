// "o" is an array of discovered objects (along with numbers, strings, functions, and plenty of holes/nulls)

// "Things" has a bunch of functions for manipulating "o".
//    Add a value with addImmediately
//    Add an expression (from fuzzer-generated code) with add or reserve
//    Find a specific object with find[Index]
//    Find a random instance of a class with instance[Index]

var o;

var Things = {
  addImmediately: function(v) {
    if (!Things.has(v)) {
      var ix = o.length;
      o[ix] = v;
      return "o[" + ix + "]";
    }
  },
  reserve: function() {
    var ix = o.length;
    o[ix] = null;
    return "o[" + ix + "]";
  },
  add: function(expr) {
    return this.reserve() + " = Things.ifNovel(" + expr + ");";
  },

  findIndex: function(needle) {
    for (var i = 0; i < o.length; ++i) {
      if (o[i] === needle) {
        return i;
      }
    }

    return -1;
  },
  find: function(needle) {
    return "o[" + Things.findIndex(needle) + "]";
  },

  has: function(v) {
    return Things.findIndex(v) != -1;
  },
  ifNovel: function(v) {
    return Things.has(v) ? null : v;
  },

  instanceIndex: function(className) {
    var classPrototype = window[className];
    if (!classPrototype)
      return -1;

    return Things.anyIndex(function(v) { return (v instanceof classPrototype); });
  },
  instance: function(className) {
    return "o[" + Things.instanceIndex(className) + "]";
  },

  hasInstance: function(className) { return Things.instanceIndex(className) != -1; },
  filterHasInstance: function(classes) { return classes.filter(function(className) { return Things.hasInstance(className); }); },
  instanceAny: function(classes) { classes = Things.filterHasInstance(classes); return Things.instance(Random.pick(classes)); },

  anyIndex: function(f) {
    if (!f) {
      // This is an inefficient way to do it...
      f = function() { return true; };
    }

    var matches = [];
    for (var i = 0; i < o.length; ++i) {
      if (f(o[i])) {
        matches.push(i);
      }
    }

    return Random.index(matches, -1);
  },
  any: function(f) {
    return "o[" + Things.anyIndex(f) + "]";
  },

  anyFunction: function() {
    return "o[" + Things.any(function(v) { return (typeof v == "function"); }) + "]";
  },

  init: function() {
    o = [0, null, undefined, window, document, function(){}, "", []];
  }
}

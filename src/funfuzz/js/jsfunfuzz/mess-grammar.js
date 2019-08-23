
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

/* exported TOTALLY_RANDOM, totallyRandom */
/* global print, Random, rnd */

// Randomly ignore the grammar 1 in TOTALLY_RANDOM times we generate any grammar node.
var TOTALLY_RANDOM = 1000;

var allMakers = getListOfMakers(this);

function totallyRandom (d, b) { /* eslint-disable-line require-jsdoc */
  d = d + (rnd(5) - 2); // can increase!!

  var maker = Random.index(allMakers);
  var val = maker(d, b);
  if (typeof val !== "string") {
    print(maker.name);
    print(maker);
    throw new Error("We generated something that isn't a string!");
  }
  return val;
}

function getListOfMakers (glob) { /* eslint-disable-line require-jsdoc */
  var r = [];
  for (var f in glob) {
    if (f.indexOf("make") === 0 && typeof glob[f] === "function" && f !== "makeFinalizeObserver" && f !== "makeFakePromise") {
      r.push(glob[f]);
    }
  }
  return r;
}

// To run testEachMaker(), replace `start(this)` with `Random.init(0);` and `testEachMaker();`
/*
function testEachMaker()
{
  for (var f of allMakers) {
    dumpln("");
    dumpln(f.name);
    dumpln("==========");
    dumpln("");
    for (var i = 0; i < 100; ++i) {
      try {
        var r = f(8, ["A", "B"]);
        if (typeof r != "string")
          throw (`Got a ${typeof r}`);
        dumpln(r);
      } catch(e) {
        dumpln("");
        dumpln(uneval(e));
        dumpln(e.stack);
        dumpln("");
        throw "testEachMaker found a bug in jsfunfuzz";
      }
    }
    dumpln("");
  }
}
*/

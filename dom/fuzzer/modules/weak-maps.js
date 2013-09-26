var fuzzerWeakMaps = (function() {
  function makeCommand()
  {
    var theMap = pick("nodes");
    var theKey = pick("nodes");
    var theValue = pick("nodes");

    switch(rnd(6)) {
    case 0:
      // Create a new weak map
      return nextSlot("nodes") + " = new WeakMap();";
    case 1:
      return theMap + ".set(" + theKey + ", " + theValue + ");";
    case 2:
      return theMap + ".delete(" + theKey + ");";
    case 3:
      return theMap + ".has(" + theKey + ");";
    case 4:
      // Get an item from the map (XXX use 'novel' or something)
      return nextSlot("nodes") + " = " + theMap + ".get(" + theKey + ");";
    case 5:
      if (rnd(200) === 0) {
        return "fuzzerWeakMaps.checkDetermism();";
      }
    default:
      // Possibly wipe out a map or key
      return theMap + " = null; " + fuzzerGC.immediate();
    }
  }

  function checkDetermism()
  {
    try {
      // Test that entries aren't prematurely dropped from the map when their
      // keys are still reachable, as this is a form of non-determinism.
      // Note that this isn't sufficient to catch all such bugs, e.g. bugs
      // involving rematerialized wrappers (see bug 655297 for an example).
      var count1 = countEntriesAll();
      dumpln("Total WeakMap entry count: " + count1);
      fuzzPriv.MP();
      fuzzPriv.MP();
      var count2 = countEntriesAll();
      if (count1 != count2) {
        dumpln("FAILURE: Total WeakMap entry count changed from " + count1 + " to " + count2);
      }
    } catch(e) {
      dumpln("checkDeterminism: " + e);
    }
  }

  function countEntriesAll()
  {
    var count = 0;
    for (var i = 0; i < all.nodes.length; ++i) {
      var m = all.nodes[i];
      if (m && typeof m == "object" && Object.getPrototypeOf(m) == WeakMap.prototype && Object.getPrototypeOf(Object.getPrototypeOf(m)) == Object.prototype) {
        count += countEntries(m);
      }
    }
    return count;
  }

  function countEntries(m)
  {
    // Count entries in WeakMap |m| that are known to the fuzzer.
    var count = 0;
    for (var j = 0; j < all.nodes.length; ++j) {
      var key = all.nodes[j];
      if (key && typeof key == "object" && m.has(key))
        ++count;
    }
    return count;
  }

  return { makeCommand: makeCommand, checkDetermism: checkDetermism };
})();

  var fuzzerTestIteration = (function() {
  function makeCommand()
  {
    if (rnd(3000) === 0)
      return "fuzzerTestIteration.testIteration();";
    return [];
  }

  function testIteration()
  {
    var checkTimer = setTimeout(check, 0);

    for (var iterI = 0; iterI < o.length; ++iterI) {
      dumpln("Testing iteration: o[" + iterI + "]");
      testObjectIteration(o[iterI]);
    }

    clearTimeout(checkTimer);
    dumpln("Iterated through the properties of all objects without any dire effects.");

    function check()
    {
      var failPrefix = (fuzzExpectSanity && !"bug 927294") ? "FAILURE: " : "";
      dumpln(failPrefix + "Iteration got stuck on o[" + iterI + "]");
    }
  }

  function testObjectIteration(obj)
  {
    if (!(obj === null || obj === undefined)) {
      try {
        for (var p in obj) {
          var j = null;
          try { j = obj[p]; } catch(e) { }
          try { "" + j; } catch(e) { } // jshint ignore:line
          try { uneval(j); } catch(e) { }
        }
      } catch(e) {
        // Once bug 564208 is fixed this could be a FAILURE
        dumpln("Odd, iterating threw:");
        dumpln(errorToString(e));
      }
    }
  }

  return {
    makeCommand: makeCommand,
    testIteration: testIteration,
    testObjectIteration: testObjectIteration,
  };
})();

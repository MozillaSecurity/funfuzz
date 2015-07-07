var fuzzerEventLoop = (function() {
  function makeCommand()
  {
    if (rnd(20) === 4) {
      // Sync XHR lets us:
      // - Spin the event loop whenever we want
      // - Inject weird behaviors into anyone else who spins the event loop
      fuzzInternalErrorsAreBugs = false; // Sync XHR can change which global is the current inner for a domwindow. See bug 804083.
      var n = 1 + rnd(30);
      var c = fuzzSubCommand("postxhr");
      return "fuzzInternalErrorsAreBugs=false/*see bug 804083*/; (function() { for (var i = 0; i < "+n+"; ++i) { var x = new XMLHttpRequest(); x.open('GET', 'data:text/html,1', false); x.send(); } })();" + c;
    } else if (rnd(19) === 4) {
      return "setTimeout(function() { " + fuzzSubCommand("timer") + " }, 0);";
    } else if (rnd(20000) === 4) {
      return "setInterval(function() { " + fuzzSubCommand("interval") + " }, 0);";
    } else if (rnd(200000) === 4) { // 100x less often because of 802477
      return "setTimeout(" + Things.anyFunction() + ", 0);";
    } else if (rnd(18) === 4) {
      return "window.mozRequestAnimationFrame(function() { " + fuzzSubCommand("raf") + " });";
    } else if (rnd(17) === 4) {
      return "window.mozRequestAnimationFrame();";
    } else if (rnd(16) === 4) {
      return "window.mozRequestAnimationFrame(" + Things.anyFunction() + ");";
    } else if (rnd(20000) === 0) {
      return "function rafc() { window.mozRequestAnimationFrame(rafc); " + fuzzSubCommand("rafc") + "} rafc();";
    } else {
      return [];
    }
  }

  return { makeCommand: makeCommand };
})();

registerModule("fuzzerEventLoop", 1);

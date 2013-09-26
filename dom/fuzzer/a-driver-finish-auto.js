(function()
{
  var timer = setInterval(checkDone, 400);

  var start = new Date();

  function checkDone()
  {
    var done = false;

    try {
      if (window.gPageCompleted) {
        dump("gPageCompleted!\n");
        done = true;
      }

      var now = new Date();

      if (now - start > 75 * 1000) {
        dump("My time is up!\n");
        done = true;
      }
    } catch(e) {
      dump("Error in checkDone\n");
      done = true;
    }

    if (done)
    {
      fuzzPriv.quitApplication();
      clearInterval(timer);
    }
  }
})();

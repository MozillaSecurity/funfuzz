var fuzzerFakeEvents = (function() {

  /*

  Tests editor more directly than execCommand("insertText") and window.getSelection().modify().

  We can also do a variety of not-very-nice things through menu items:

  * Open the bookmarks manager
  * Open Page Info
  * Minimize the window
  * Navigate away (Alt+Home, etc)
  * Focus the address bar
  * Cut, copy or paste (XXX not sure this works)
  * Steal form autocomplete history
  * Activate "user" full screen
  * Activate developer tools

  But we probably can't do extensive damage, because subsequent keystrokes still are targeted at this page.

  */

  var isMac = navigator.platform.indexOf("Mac") != -1;

  function isDestructiveCharCode(n) {
    var ch = String.fromCharCode(n).toUpperCase();
    return (ch == 'R' || ch == 'W' || ch == 'Q' || ch == 'P' || ch == 'S');
  }

  function makeCommand()
  {
    var target = rnd(8) ? "document.activeElement" : pick("nodes");

    var type;
    var keyCode = 0;
    var charCode = 0;

    var ctrl = false;
    var alt = false;
    var shift = false;
    var meta = false;

    var destructiveNote = "";

    if (rnd(100) === 0) return "document.documentElement.contentEditable = true;";
    if (rnd(100) === 0) return "window.focus();";

    if (rnd(4)) {
      // Navigation within an editable area.

      type = "press";
      keyCode = 33 + rnd(8); // pgup, pgdn, end, home, left, up, right, down

      // Modifiers for arrow keys vary by platform.
      if (keyCode >= 37 && rnd(2)) {
        if (isMac) {
          // On Mac, holding Cmd turns it into Line-{Home,End} or Document-{Home,End}, while holding Alt moves by word.
          if (rnd(3)) {
            alt = true;
          } else {
            meta = true;
          }
        } else {
          // On non-Mac, holding Ctrl moves by word.
          ctrl = true;
        }
      }

      // Holding shift extends the selection
      shift = rnd(2) === 0;

      // Also consider on Mac and Linux: Ctrl+A, Ctrl+E (but only without Shift!)
      // Also consider on Windows: Ctrl+Home to for Document-Home??
    } else {
      // Do something weird!

      type = rnd(5) ? "press" : rnd(2) ? "down" : "up";

      // In Gecko,
      // * a typical keypress event will have a keyCode if printable, and a charCode otherwise.
      // * a typical keydown event will have a charCode.
      if (type != "press" || rnd(2)) {
        keyCode = rnd(256);
      } else {
        charCode = randomThing(fuzzValues.chars).charCodeAt(0); // assuming BMP (astral doesn't work here anyway)
      }

      if (rnd(5)) {
        ctrl  = rnd(7) === 0;
        alt   = rnd(7) === 0;
        shift = rnd(2) === 0;
        meta  = rnd(7) === 0;
      }

      // Avoid reloading the page, etc
      if (isDestructiveCharCode(charCode)) {
        destructiveNote = "/* Destructive with accel */";
      }
      if (keyCode == 116) {
        destructiveNote = "/* Destructive: F5 (reload) */";
      }
      if (keyCode == 36 && alt) {
        destructiveNote = "/* Destructive: Alt+Home (navigate to home page) */";
      }
      if (destructiveNote && rnd(10000)) {
        return [];
      }

    }

    var keyCodeWithNote = keyCode && ("/*keyCode*/" + keyCode);
    var chearCodeWithNote = charCode && ("/*charCode*/" + charCode);

    return ("setTimeout(function() { " + destructiveNote + "fuzzPriv.trustedKeyEvent(" +
      target + ", " + simpleSource(type) + ", " + ctrl + ", " + alt + ", " + shift + ", " + meta + ", " + keyCodeWithNote + ", " + chearCodeWithNote
    + "); }, 0);");
  }

  return { makeCommand: makeCommand };
})();


// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

/* exported confused, errorstack, errorToString, foundABug */
/* global dumpln, jsshell, print, printImportant, quit */

function confused (s) { /* eslint-disable-line require-jsdoc */
  if (jsshell) {
    // Magic string that js_interesting looks for
    // Currently disabled until its use can be figured out
    // print("jsfunfuzz broke" + " its own scripting environment: " + s);
    // Replaced with the following:
    print(`jsfunfuzz got confused: ${s}`);
    quit();
  }
}

function foundABug (summary, details) { /* eslint-disable-line require-jsdoc */
  // Magic pair of strings that js_interesting looks for
  // Break up the following string so internal js functions do not print it deliberately
  let foundMsg = `Found`;
  foundMsg += ` a bug: ${summary}`;
  printImportant(foundMsg);
  if (details) {
    printImportant(details);
  }
  if (jsshell) {
    dumpln("jsfunfuzz stopping due to finding a bug.");
    quit();
  }
}

function errorToString (e) { /* eslint-disable-line require-jsdoc */
  try {
    return (`${e}`);
  } catch (e2) {
    return "Can't toString the error!!";
  }
}

function errorstack () { /* eslint-disable-line require-jsdoc */
  print("EEE");
  try {
    void ([].qwerty.qwerty);
  } catch (e) { print(e.stack); }
}

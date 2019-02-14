
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

/* global dumpln, jsshell, print, printImportant, quit */

function confused(s)
{
  if (jsshell) {
    // Magic string that js_interesting looks for
    // Currently disabled until its use can be figured out
    // print("jsfunfuzz broke" + " its own scripting environment: " + s);
    // Replaced with the following:
    print("jsfunfuzz got confused: " + s);
    quit();
  }
}

function foundABug(summary, details)
{
  // Magic pair of strings that js_interesting looks for
  // Break up the following string so internal js functions do not print it deliberately
  printImportant("Found" + " a bug: " + summary);
  if (details) 
    printImportant(details);
  
  if (jsshell) {
    dumpln("jsfunfuzz stopping due to finding a bug.");
    quit();
  }
}

function errorToString(e)
{
  try {
    return ("" + e);
  } catch (e2) {
    return "Can't toString the error!!";
  }
}

function errorstack()
{
  print("EEE");
  try {
    void ([].qwerty.qwerty);
  } catch (e) { print(e.stack); }
}

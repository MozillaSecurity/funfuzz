var count = 0;
var verbose = false;


// https://bugzilla.mozilla.org/show_bug.cgi?id=394853#c19
//try { eval("/") } catch(e) { }
// Remember the number of countHeap.
tryItOut("");



/**************************************
 * To reproduce a crash or assertion: *
 **************************************/

// 1. grep tryIt LOGFILE | grep -v "function tryIt" | pbcopy
// 2. Paste the result between "ddbegin" and "ddend", replacing "start(this);"
// 3. Run Lithium to remove unnecessary lines between "ddbegin" and "ddend".
// SPLICE DDBEGIN
start(this);
// SPLICE DDEND

if (jsshell)
  print("It's looking good!"); // Magic string that jsInteresting.py looks for


// 3. Run it.

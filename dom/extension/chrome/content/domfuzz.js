(function() { // just for scoping

function dumpln(s) { dump(s + "\n"); }

// readFile function from logan
// http://www.gozer.org/mozilla/userChrome.js/scripts/userScripts.uc.js
// |file| must be an nsIFile.
// Returns the contents of the file as a string.
function readFile(file)
{
  var content = '';

  var stream = Components.classes['@mozilla.org/network/file-input-stream;1']
                    .createInstance(Components.interfaces.nsIFileInputStream);
  stream.init(file, 0x01, 0, 0);

  var script = Components.classes['@mozilla.org/scriptableinputstream;1']
              .createInstance(Components.interfaces.nsIScriptableInputStream);
  script.init(stream);

  if (stream.available()) {
    var data = script.read(4096);

    while (data.length > 0) {
      content += data;
      data = script.read(4096);
    }
  }

  stream.close();
  script.close();

  return content;
}


// http://developer.mozilla.org/en/docs/Code_snippets:On_page_load
// https://bugzilla.mozilla.org/show_bug.cgi?id=329514

window.addEventListener("load", domFuzzInit, false);

function domFuzzInit(event)
{
  window.removeEventListener("load", domFuzzInit, false);

  var appcontent = document.getElementById("appcontent");
  appcontent.addEventListener("load", onPageLoad, true);
}

function onPageLoad(event)
{
  var doc = event.originalTarget;
  if (doc.nodeName != "#document")
    return;

  var hash = doc.location.hash;

  var r = hash.split(",");

  if (r[0] == "#squarefree-autoquit") {
    dump("Quitting in 1 second\n");
    setTimeout(goQuitApplication, 1000);
    return;
  }
  else if (r[0] != "#squarefree-af") {
    return;
  }
  if (!(/^[a-zA-Z0-9\-.]*$/.test(r[1]))) {
    dump("Sketchy fuzzer filename!\n");
    return;
  }

  var d = Components.classes["@mozilla.org/file/directory_service;1"]
                    .getService(Components.interfaces.nsIProperties)
                    .get("ProfD", Components.interfaces.nsIFile);

  d.append("extensions");
  d.append("domfuzz@squarefree.com");

  var extensionLocation = readFile(d).replace(/\s*$/, "");

  var f = Components.classes["@mozilla.org/file/local;1"]
                    .createInstance(Components.interfaces.nsILocalFile);
  f.initWithPath(extensionLocation);

  var dir = f.parent;
  dir.append("fuzzers");
  // dir now points to the directory containing fuzzer-combined.js, etc.

  var scriptToInject =
    readFile(indir(dir, "fuzz.js")) + "\n"
  + readFile(indir(dir, r[1])) + "\n"
  + readFile(indir(dir, "fuzz-finish-auto.js")) + "\n"
  + "document.getElementById('fuzz1').parentNode.removeChild(document.getElementById('fuzz1'));\n"
  + "fuzzSettings = [" + r.slice(2).join(",") + "];\n"
  + "setTimeout(fuzzOnload, 400);\n";

  var insertionPoint = doc.getElementsByTagName("head")[0] || doc.documentElement;

  if (!insertionPoint)
    return;

  var script = doc.createElementNS("http://www.w3.org/1999/xhtml", "script");
  script.setAttribute("id", "fuzz1");
  script.setAttribute("type", "text/javascript");
  script.textContent = scriptToInject;
  insertionPoint.appendChild(script);
}

function indir(dir, filename)
{
  var d = dir.clone();
  d.append(filename);
  return d;
}



/********
 * QUIT *
 ********/

// From quit.js, which Bob Clary extracted from mozilla/toolkit/content

function canQuitApplication()
{
  var os = Components.classes["@mozilla.org/observer-service;1"]
    .getService(Components.interfaces.nsIObserverService);
  if (!os)
  {
    return true;
  }

  try
 {
    var cancelQuit = Components.classes["@mozilla.org/supports-PRBool;1"]
      .createInstance(Components.interfaces.nsISupportsPRBool);
    os.notifyObservers(cancelQuit, "quit-application-requested", null);

    // Something aborted the quit process.
    if (cancelQuit.data)
    {
      return false;
    }
  }
  catch (ex)
  {
  }
  os.notifyObservers(null, "quit-application-granted", null);
  return true;
}

function goQuitApplication()
{
  dumpln("goQuitApplication (overlay)");

  if (!canQuitApplication())
  {
    return false;
  }

  var kAppStartup = '@mozilla.org/toolkit/app-startup;1';
  var kAppShell   = '@mozilla.org/appshell/appShellService;1';
  var   appService;
  var   forceQuit;

  if (kAppStartup in Components.classes)
  {
    appService = Components.classes[kAppStartup].
      getService(Components.interfaces.nsIAppStartup);
    forceQuit  = Components.interfaces.nsIAppStartup.eForceQuit;

  }
  else if (kAppShell in Components.classes)
  {
    appService = Components.classes[kAppShell].
      getService(Components.interfaces.nsIAppShellService);
    forceQuit = Components.interfaces.nsIAppShellService.eForceQuit;
  }
  else
  {
    throw 'goQuitApplication: no AppStartup/appShell';
  }

  var windowManager = Components.
    classes['@mozilla.org/appshell/window-mediator;1'].getService();

  var windowManagerInterface = windowManager.
    QueryInterface(Components.interfaces.nsIWindowMediator);

  var enumerator = windowManagerInterface.getEnumerator(null);

  while (enumerator.hasMoreElements())
  {
    var domWindow = enumerator.getNext();
    if (("tryToClose" in domWindow) && !domWindow.tryToClose())
    {
      return false;
    }
    domWindow.close();
  }

  try
  {
    appService.quit(forceQuit);
  }
  catch(ex)
  {
    throw('goQuitApplication: ' + ex);
  }

  return true;
}




})();//end scoping


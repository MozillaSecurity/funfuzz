(function() { // just for scoping

function dumpln(s) { dump(s + "\n"); }

// readFile fnuction from logan
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
  
  
  // http://developer.mozilla.org/en/docs/Code_snippets:Interaction_between_privileged_and_non-privileged_pages
  // Setting the last argument to |true| means we're allowing untrusted events to trigger this chrome event handler.
  window.addEventListener("please-quit", pleaseQuitCalled, true, true);
  window.addEventListener("please-gc", pleaseGCCalled, true, true);
  window.addEventListener("please-run-soon", pleaseRunSoonCalled, true, true);
  
}

function onPageLoad(event)
{
  var doc = event.originalTarget;
  if (doc.nodeName != "#document")
    return;

  var hash = doc.location.hash;

  var r = hash.split("!");

  if (r[0] != "#squarefree-af")
    return;
  if (!(/^[a-zA-Z0-9\-.]*$/.test(r[1]))) {
    dump("Sketchy fuzzer filename!\n");
    return;
  }

  // I hope having this event listener doesn't have side effects!
  doc.addEventListener("pagehide", quitPageHide, false);
  
  var d = Components.classes["@mozilla.org/file/directory_service;1"]
                    .getService(Components.interfaces.nsIProperties)
                    .get("ProfD", Components.interfaces.nsIFile);

  d.append("extensions");
  d.append("domfuzz@squarefree.com");
  
  var extensionLocation = readFile(d).replace(/\s*$/, "");
  
  var f = Components.classes["@mozilla.org/file/local;1"]
                    .createInstance(Components.interfaces.nsILocalFile);
  f.initWithPath(extensionLocation);

  dir = f.parent;
  dir.append("fuzzers");
  // dir now points to the directory containing fuzzer-combined.js, etc.

  var scriptToInject = 
    readFile(indir(dir, "fuzz.js")) + "\n"
  + readFile(indir(dir, r[1])) + "\n"
  + readFile(indir(dir, "fuzz-finish-auto.js")) + "\n"
  + "document.getElementById('fuzz1').parentNode.removeChild(document.getElementById('fuzz1'));\n"
  + "fuzzSettings = [" + r[2] + "];\n"
  + "setTimeout(fuzzOnload, 400);\n";

  insertionPoint = doc.getElementsByTagName("head")[0] || doc.documentElement;
  
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

/*
function quitTimeout()
{
  dump("Quitting due to timeout.\n");
  goQuitApplication();
}
*/

function quitPageHide()
{
  dumpln("Quitting due to pagehide.\n");
  goQuitApplication();
}

function pleaseQuitCalled()
{
  dump("Quitting because I got a please-quit event from the web page.\n");
  goQuitApplication();
}

function pleaseGCCalled()
{ 
  dump("GC!\n");
  Components.utils.forceGC();

  window.QueryInterface(Components.interfaces.nsIInterfaceRequestor)
        .getInterface(Components.interfaces.nsIDOMWindowUtils)
        .garbageCollect(); 
  window.QueryInterface(Components.interfaces.nsIInterfaceRequestor)
        .getInterface(Components.interfaces.nsIDOMWindowUtils)
        .garbageCollect(); 
  window.QueryInterface(Components.interfaces.nsIInterfaceRequestor)
        .getInterface(Components.interfaces.nsIDOMWindowUtils)
        .garbageCollect(); 
}

// Stick an event on the thread's queue.
// Useful for precise interactions with interruptible reflow (much more precise than setTimeout);
// also potentially faster than setTimeout (which always takes at least 10ms).
// Based on "executeSoon" in
// http://mxr.mozilla.org/mozilla-central/source/testing/mochitest/tests/SimpleTest/SimpleTest.js
function pleaseRunSoonCalled(event)
{
  var target = event.originalTarget;
  var detail = event.detail; // an opaque string that is returned to the page
  var tm = Components.classes["@mozilla.org/thread-manager;1"]
             .getService(Components.interfaces.nsIThreadManager);

  tm.mainThread.dispatch({
    run: function() {
      dispatchBackToPage(target, detail);
    }
  }, Components.interfaces.nsIThread.DISPATCH_NORMAL);
}

function dispatchBackToPage(target, detail)
{
  //dumpln("Dispatching back to page: " + target + " " + detail);
  var evt = document.createEvent("Events");
  evt.detail = detail;
  evt.initEvent("run-now", true, false);
  target.dispatchEvent(evt);
}


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
  var privs = 'UniversalPreferencesRead UniversalPreferencesWrite ' +
    'UniversalXPConnect';

  try
  {
    netscape.security.PrivilegeManager.enablePrivilege(privs);
  }
  catch(ex)
  {
    throw('goQuitApplication: privilege failure ' + ex);
  }

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


})();


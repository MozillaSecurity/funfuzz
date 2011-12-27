"use strict";

const Cu = Components.utils;
const Cc = Components.classes;
const Ci = Components.interfaces;

Cu.import("resource://gre/modules/XPCOMUtils.jsm");
Cu.import("resource://gre/modules/Services.jsm");
Cu.import("resource://gre/modules/NetUtil.jsm");

function dumpln(s) { dump(s + "\n"); }

const CHILD_SCRIPT = "chrome://domfuzzhelper/content/domfuzzhelper.js";

/*****************
 * API INJECTION *
 *****************/

// Based on:
// https://bug549539.bugzilla.mozilla.org/attachment.cgi?id=429661
// https://developer.mozilla.org/en/XPCOM/XPCOM_changes_in_Gecko_1.9.3
// http://mxr.mozilla.org/mozilla-central/source/toolkit/components/console/hudservice/HUDService.jsm#3240
// https://developer.mozilla.org/en/how_to_build_an_xpcom_component_in_javascript

function DOMFuzzHelperObserver() {
  this._isFrameScriptLoaded = false;
}

// Use runSoon to avoid false-positive leaks due to content JS on the stack (?)
function quitFromContent() { dumpln("Page called quitApplication."); runSoon(quitOnce); }
function quitApplicationSoon() { dumpln("Page called quitApplicationSoon."); runOnTimer(quitOnce); }

DOMFuzzHelperObserver.prototype = {
  classDescription: "DOM fuzz helper observer",
  classID:          Components.ID("{73DD0F4A-B201-44A1-8C56-D1D72432B02A}"),
  contractID:       "@squarefree.com/dom-fuzz-helper-observer;1",
  _xpcom_categories: [{category: "profile-after-change", service: true }],

  //QueryInterface:   XPCOMUtils.generateQI([Ci.nsIDOMGlobalPropertyInitializer]),
  QueryInterface:   XPCOMUtils.generateQI([Ci.nsIObserver]),

  observe: function(aSubject, aTopic, aData) {
    if (aTopic == "profile-after-change") {
      this.init();
    } else if (!this.isFrameScriptLoaded && aTopic == "chrome-document-global-created") {

      var messageManager = Cc["@mozilla.org/globalmessagemanager;1"].
                               getService(Ci.nsIChromeFrameMessageManager);

      // Register for any messages our API needs us to handle
      messageManager.addMessageListener("DOMFuzzHelper.quitApplication", this);
      messageManager.addMessageListener("DOMFuzzHelper.quitApplicationSoon", this);
      messageManager.addMessageListener("DOMFuzzHelper.quitWithLeakCheck", this);
      messageManager.addMessageListener("DOMFuzzHelper.setGCZeal", this);
      messageManager.addMessageListener("DOMFuzzHelper.getProfileDirectory", this);
      messageManager.addMessageListener("DOMFuzzHelper.getBinDirectory", this);
      messageManager.addMessageListener("DOMFuzzHelper.openAboutMemory", this);
      messageManager.loadFrameScript(CHILD_SCRIPT, true);

      this.isFrameScriptLoaded = true;

    } else if (aTopic == "xpcom-shutdown") {
        this.uninit();
    }
  },

  init: function() {
    var obs = Services.obs;

    obs.addObserver(this, "xpcom-shutdown", false);
    obs.addObserver(this, "chrome-document-global-created", false);
  },

  uninit: function() {
    var obs = Services.obs;

    obs.removeObserver(this, "chrome-document-global-created", false);
  },

  /**
    * messageManager callback function
    * This will get requests from our API in the window and process them in chrome for it
    **/

  receiveMessage: function(aMessage) {
    switch(aMessage.name) {
      case "DOMFuzzHelper.quitApplication":
        quitFromContent();
        break;

      case "DOMFuzzHelper.quitApplicationSoon":
        quitApplicationSoon();
        break;

      case "DOMFuzzHelper.quitWithLeakCheck":
        quitWithLeakCheck();
        break;

      case "DOMFuzzHelper.setGCZeal":
        setGCZeal(aMessage.json.zeal);
        break;

      case "DOMFuzzHelper.getProfileDirectory":
        return getProfileDirectory();

      case "DOMFuzzHelper.getBinDirectory":
        return getBinDirectory();

      case "DOMFuzzHelper.openAboutMemory":
        openAboutMemory();
        break;

      default:
        dumpln("Unrecognized message sent to domfuzzhelperobserver.js");

    }
  }
};

const NSGetFactory = XPCOMUtils.generateNSGetFactory([DOMFuzzHelperObserver]);


/********************************************
 * MISC PRIVILEGED FUNCTIONS - MAIN PROCESS *
 ********************************************/

function runSoon(f)
{
  var tm = Components.classes["@mozilla.org/thread-manager;1"]
             .getService(Components.interfaces.nsIThreadManager);

  tm.mainThread.dispatch({
    run: function() {
      f();
    }
  }, Components.interfaces.nsIThread.DISPATCH_NORMAL);
}



function setGCZeal(zeal)
{
  if (typeof(zeal) == "number") {
    Services.prefs.setIntPref("javascript.options.gczeal", zeal)
  }
}

function getProfileDirectory()
{
  var d = Components.classes["@mozilla.org/file/directory_service;1"]
                    .getService(Components.interfaces.nsIProperties)
                    .get("ProfD", Components.interfaces.nsIFile);
  return d.path;
}

function getBinDirectory()
{
  var d = Components.classes["@mozilla.org/file/directory_service;1"]
                    .getService(Components.interfaces.nsIProperties)
                    .get("CurProcD", Components.interfaces.nsIFile);
  return d.path;
}

function openAboutMemory()
{
  var ww = Components.classes["@mozilla.org/embedcomp/window-watcher;1"]
                     .getService(Ci.nsIWindowWatcher);

  ww.openWindow(null, "about:memory", null, "width=200,height=200", null);
}


/************************
 * QUIT WITH LEAK CHECK *
 ************************/

var quitting = false;

function quitWithLeakCheck(leaveWindowsOpen)
{
  leaveWindowsOpen = !!leaveWindowsOpen;

  // Magic string that rundomfuzz.py looks for
  var messagePrefix = "Leaked until " + (leaveWindowsOpen ? "tab close" : "shutdown");

  if (quitting)
    return;
  quitting = true;

  runSoon(a);
  function a() { dumpln("QA"); if (!leaveWindowsOpen) closeAllWindows(); runOnTimer(b); dumpln("QAA"); }
  function b() { dumpln("QB"); mpUntilDone(c); }
  function c() { dumpln("QC"); bloatStats(d); }
  function d(objectCounts) {
    dumpln("QD");

    // Mac normally has extra documents (due to the hidden window?)
    var isMac = Cc["@mozilla.org/xre/app-info;1"].getService(Ci.nsIXULRuntime).OS == "Darwin";

    var expected = {
      'nsGlobalWindow':          4 + 6*leaveWindowsOpen,
      'nsDocument':              4 + 4*isMac + 24*leaveWindowsOpen,
      'nsDocShell':              5,
      'BackstagePass':           1,
      'nsGenericElement':        1927,
      'nsHTMLDivElement':        4,
      'xpc::CompartmentPrivate': 3,
    }

    for (var p in expected) {
      if (objectCounts[p] > expected[p]) {
        dumpln(messagePrefix + ": " + p + "(" + objectCounts[p] + " > " + expected[p] + ")");
      } else if (objectCounts[p] < expected[p]) {
        dumpln("That's odd"  + ": " + p + "(" + objectCounts[p] + " < " + expected[p] + ")");
      }
    }

    runSoon(e);
  }
  function e() { dumpln("QE"); quitOnce(); }
}

var timerDeathGrip;
function runOnTimer(f)
{
    timerDeathGrip = Components.classes["@mozilla.org/timer;1"].createInstance(Components.interfaces.nsITimer);
    timerDeathGrip.initWithCallback({notify: function(){ timerDeathGrip=null; f(); }}, 2000, Components.interfaces.nsITimer.TYPE_ONE_SHOT);
}

function closeAllWindows()
{
  var ww = Components.classes["@mozilla.org/embedcomp/window-watcher;1"]
                     .getService(Ci.nsIWindowWatcher);
  var enumerator = ww.getWindowEnumerator();

  var windowsToClose = [];

  while (enumerator.hasMoreElements()) {
    windowsToClose.push(enumerator.getNext().QueryInterface(Ci.nsIDOMWindow));
  }

  // if not mac...
  ww.openWindow(null, "about:blank", null, "width=200,height=200", null);

  for (var i = 0; i < windowsToClose.length; ++i) {
    windowsToClose[i].close();
  }

  dumpln("1");
}

function mpUntilDone(callback)
{
  function mpUntilDoneInner()
  {
    dumpln("MP " + j);
    sendMemoryPressureNotification();

    ++j;
    if (j > 9)
      runSoon(callback);
    else if (j % 2 == 1 && typeof Components.utils.schedulePreciseGC == "function")
      Components.utils.schedulePreciseGC(mpUntilDoneInner)
    else
      runSoon(mpUntilDoneInner);
  }

  var j = 0;
  mpUntilDoneInner();
}


/*
     |<----------------Class--------------->|<-----Bytes------>|<----------------Objects---------------->|<--------------References-------------->|
                                              Per-Inst   Leaked    Total      Rem      Mean       StdDev     Total      Rem      Mean       StdDev

*/
// Grab the class name and the number of remaining objects.
var bloatRex = /\s*\d+\s+(\S+)\s+\d+\s+\d+\s+\d+\s+(\d+)\s+.*/;
const SET_QUOTA = false;
const USE_QUOTA = false;

function bloatStats(callback)
{
  var objectCounts = {};

  try {
    //d.d.d;
    NetUtil.asyncFetch("about:bloat", fetched);
  } catch(e) {
    dumpln("Can't open about:bloat -- maybe you forgot to use XPCOM_MEM_LEAK_LOG");
    callback(objectCounts);
  }

  function fetched(aInputStream, aResult)
  {
    var r = NetUtil.readInputStreamToString(aInputStream, aInputStream.available());
    var lines = r.split("\n");
    for (var i = 0; i < lines.length; ++i)
    {
      var a = bloatRex.exec(lines[i]);
      if (a) {
        if (SET_QUOTA) {
          dumpln("'" + a[1] + "': " + a[2] + ",");
        } else if (USE_QUOTA) {
          var quotaA = QUOTA[a[1]] || 0;
          if (a[2] > quotaA) { dumpln("Leak? Too many " + a[1] + " (" + a[2] + " > " + quotaA + ")"); }
        }
        objectCounts[a[1]] = a[2];
      }
    }
    runSoon(callCallback);
  }

  function callCallback()
  {
    callback(objectCounts)
  }
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
  dumpln("goQuitApplication (domfuzzhelperobserver.js component)");

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

var alreadyQuitting = false;
function quitOnce()
{
  if (!alreadyQuitting) {
    alreadyQuitting = true;
    goQuitApplication();
  }
}

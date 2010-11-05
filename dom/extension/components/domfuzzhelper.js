Components.utils.import("resource://gre/modules/XPCOMUtils.jsm");

// Based on:
// https://bug549539.bugzilla.mozilla.org/attachment.cgi?id=429661
// https://developer.mozilla.org/en/XPCOM/XPCOM_changes_in_Gecko_1.9.3
// http://mxr.mozilla.org/mozilla-central/source/toolkit/components/console/hudservice/HUDService.jsm#3240
// https://developer.mozilla.org/en/how_to_build_an_xpcom_component_in_javascript



const Cc = Components.classes;
const Ci = Components.interfaces;

function dumpln(s) { dump(s + "\n"); }

function DOMFuzzHelper() {}

DOMFuzzHelper.prototype = {
  classDescription: "DOM fuzz helper",
  classID:          Components.ID("{59a52458-13e0-4d90-9d85-a637344f29a1}"),
  contractID:       "@squarefree.com/dom-fuzz-helper;1",

  QueryInterface:   XPCOMUtils.generateQI([Components.interfaces.nsIObserver]),
  _xpcom_categories: [{category: "profile-after-change", service: true }],

  observe: function(aSubject, aTopic, aData)
  {
    if (aTopic == "profile-after-change") {
      this.init();
    } else if (aTopic == "content-document-global-created") {
      var w = aSubject.wrappedJSObject;

      if (w) {
        w.goQuitApplication = function() { runSoon(goQuitApplication); }; // using runSoon avoids leaks (bug 593541)
        w.fuzzPrivRunSoon = runSoon;
        //w.fuzzPrivEnableAccessibility = enableAccessibility; // bug 571613, bug 404077, bug 571530
        w.fuzzPrivGC = function() { Components.utils.forceGC(); };
        w.fuzzPrivMP = sendMemoryPressureNotification;
        w.fuzzPrivCC = cycleCollect(aSubject);
        w.fuzzPrivZoom = setZoomLevel(aSubject);
        w.fuzzPrivPrintToFile = printToFile(aSubject);
      } else {
        // I don't understand why this happens.  Some chrome windows sneak in here?
      }
    } else if (aTopic == "xpcom-shutdown") {
      this.uninit();
    }
  },

  init: function()
  {
    var obs = Cc["@mozilla.org/observer-service;1"].getService(Ci.nsIObserverService);
    obs.addObserver(this, "xpcom-shutdown", false);
    obs.addObserver(this, "content-document-global-created", false);
  },

  uninit: function()
  {
    var obs = Cc["@mozilla.org/observer-service;1"].getService(Ci.nsIObserverService);
    obs.removeObserver(this, "content-document-global-created");
  },
};

const NSGetFactory = XPCOMUtils.generateNSGetFactory([DOMFuzzHelper]);



/*****************************
 * MISC PRIVILEGED FUNCTIONS *
 *****************************/

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


function enableAccessibility()
{
  try {
    Components.classes["@mozilla.org/accessibilityService;1"]
      .getService(Components.interfaces.nsIAccessibleRetrieval);
    dump("Enabled accessibility!\n");
  } catch(e) {
    dump("Couldn't enable accessibility: " + e + "\n");
  }
}

function sendMemoryPressureNotification()
{
  var os = Components.classes["@mozilla.org/observer-service;1"]
           .getService(Components.interfaces.nsIObserverService);
  os.notifyObservers(null, "memory-pressure", "heap-minimize");
}

function cycleCollect(window)
{
  return function cycleCollectInner() {
    window.QueryInterface(Components.interfaces.nsIInterfaceRequestor)
          .getInterface(Components.interfaces.nsIDOMWindowUtils)
          .garbageCollect();
  }
}

function setZoomLevel(window)
{
  return function setZoomLevelInner(textOrFull, factor) {
    var viewer = window.QueryInterface(Components.interfaces.nsIInterfaceRequestor)
                       .getInterface(Components.interfaces.nsIWebNavigation)
                       .QueryInterface(Components.interfaces.nsIDocShell)
                       .contentViewer
                       .QueryInterface(Components.interfaces.nsIMarkupDocumentViewer);

    if (textOrFull == "text")
      viewer.textZoom = +factor;
    else if (textOrFull == "full")
      viewer.fullZoom = +factor;
  }
}

function printToFile(window)
{
  // Linux: tested, works for PDF and PS, oddly asynchronous.
  // Mac: tested, printToFile is ignored and it goes to a printer!
  // Windows: untested.
  var xulRuntime = Components.classes["@mozilla.org/xre/app-info;1"]
                             .getService(Components.interfaces.nsIXULRuntime);
  if (xulRuntime.OS != "Linux") return function() { };

  var fired = false;

  return function printToFileInner(showHeaders, showBGColor, showBGImages, ps) {
    runSoon(function() {
        // Don't print more than once, it gets messy fast.
        if (fired) { return false; }
        fired = true;

        // Based on https://addons.mozilla.org/en-US/firefox/addon/5971/ by pav and bho

        var webBrowserPrint = window.QueryInterface(Components.interfaces.nsIInterfaceRequestor)
        .getInterface(Components.interfaces.nsIWebBrowserPrint);

        var nsIPrintSettings = Components.interfaces.nsIPrintSettings;

        var PSSVC = Components.classes["@mozilla.org/gfx/printsettings-service;1"]
        .getService(Components.interfaces.nsIPrintSettingsService);

        var printSettings = PSSVC.newPrintSettings;

        var file = Components.classes["@mozilla.org/file/directory_service;1"].
                              getService(Components.interfaces.nsIProperties).
                              get("ProfD", Components.interfaces.nsIFile);
        file.append(ps ? "a.ps" : "a.pdf");
        dumpln("Printing to: " + file.path);

        printSettings.printToFile = true;
        printSettings.toFileName  = file.path;
        printSettings.printSilent = true;
        printSettings.outputFormat = ps ? nsIPrintSettings.kOutputFormatPS : nsIPrintSettings.kOutputFormatPDF;
        printSettings.printBGColors   = !!showBGColor;
        printSettings.printBGImages   = !!showBGImages;
        if (!showHeaders) {
            printSettings.footerStrCenter = '';
            printSettings.footerStrLeft   = '';
            printSettings.footerStrRight  = '';
            printSettings.headerStrCenter = '';
            printSettings.headerStrLeft   = '';
            printSettings.headerStrRight  = '';
        }

        webBrowserPrint.print(printSettings, null);
    });
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
  dumpln("goQuitApplication (js component)");

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

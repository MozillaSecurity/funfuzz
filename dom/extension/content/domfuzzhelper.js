"use strict";

const Cu = Components.utils;
const Cc = Components.classes;
const Ci = Components.interfaces;

function dumpln(s) { dump(s + "\n"); }

// content script for e10s support

// This is a frame script, so it may be running in a content process.
// In any event, it is targeted at a specific "tab", so we listen for
// the DOMWindowCreated event to be notified about content windows
// being created in this context.

function DOMFuzzHelperManager() {
  addEventListener("DOMWindowCreated", this, false);
}

DOMFuzzHelperManager.prototype = {
  handleEvent: function handleEvent(aEvent) {
    var window = aEvent.target.defaultView;
    window.wrappedJSObject.fuzzPriv = makeDOMFuzzHelper(window);
    window.addEventListener("load", maybeInjectScript, false);
  }
};

var domfuzzhelpermanager = new DOMFuzzHelperManager();


/*****************************
 * FUZZPRIV OBJECT INJECTION *
 *****************************/

// Create deeply fresh objects so windows don't influence each other.

function makeDOMFuzzHelper(aWindow) {
  dumpln("DOMFuzzHelper created");

  return {
      toString: function() { return "[DOMFuzzHelper]"; },

      quitApplication: function() {
        sendAsyncMessage('DOMFuzzHelper.quitApplication', {});
      },

      quitApplicationSoon: function() {
        sendAsyncMessage('DOMFuzzHelper.quitApplicationSoon', {});
      },

      closeTabThenQuit: function () {
        content.close();
        sendAsyncMessage('DOMFuzzHelper.quitApplicationSoon', {});
      },

      quitWithLeakCheck: function () {
        sendAsyncMessage('DOMFuzzHelper.quitWithLeakCheck', {});
      },

      setGCZeal: function(zeal) {
        sendSyncMessage("DOMFuzzHelper.setGCZeal", {'zeal' : zeal});
      },

      runSoon: runSoon.bind(this),

      enableAccessibility: enableAccessibility.bind(this),

      GC: function() { Cu.forceGC(); },

      CC: cycleCollect(aWindow),

      MP: sendMemoryPressureNotification.bind(this),

      fontList: fontList.bind(this),

      reftestList: reftestList.bind(this),

      printToFile: printToFile(aWindow),

      openAboutMemory: function() {
        content.open("about:memory");
      },

      __exposedProps__: {
        'toString': 'r',
        'quitApplication': 'r',
        'quitApplicationSoon': 'r',
        'closeTabThenQuit': 'r',
        'quitWithLeakCheck': 'r',
        'setGCZeal': 'r',
        'runSoon': 'r',
        'enableAccessibility': 'r',
        'GC': 'r',
        'CC': 'r',
        'MP': 'r',
        'fontList': 'r',
        'printToFile': 'r',
        'openAboutMemory': 'r',
        'reftestList': 'r'
      }
  };
};


/***********************************************
 * MISC PRIVILEGED FUNCTIONS - CONTENT PROCESS *
 ***********************************************/

function runSoon(f)
{
  var tm = Cc["@mozilla.org/thread-manager;1"]
             .getService(Ci.nsIThreadManager);

  tm.mainThread.dispatch({
    run: function() {
      f();
    }
  }, Ci.nsIThread.DISPATCH_NORMAL);
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
          .cycleCollect();
  }
}

/*
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
*/

function printToFile(window)
{
  // Oddly asynchronous, at least on Linux.

  // Linux: works for PDF and PS.
  // Windows: works for PDF at least. Text may be invisible (bug 653336).
  // Mac: tested, printToFile is ignored and it goes to a printer!
  var xulRuntime = Components.classes["@mozilla.org/xre/app-info;1"]
                             .getService(Components.interfaces.nsIXULRuntime);
  dumpln("xulRuntime.OS: " + xulRuntime.OS);
  if (xulRuntime.OS != "Linux" && xulRuntime.OS != "WINNT") return function() { };

  var fired = false;

  return function printToFileInner(showHeaders, showBGColor, showBGImages, ps) {
    runSoon(function() {
        // Don't print more than once, it gets messy fast.
        if (fired) { return false; }
        fired = true;

        // Based on https://addons.mozilla.org/en-US/firefox/addon/5971/ by pavlov (Stuart Parmenter) and bho

        var webBrowserPrint = window.QueryInterface(Components.interfaces.nsIInterfaceRequestor)
        .getInterface(Components.interfaces.nsIWebBrowserPrint);

        var nsIPrintSettings = Components.interfaces.nsIPrintSettings;

        var PSSVC = Components.classes["@mozilla.org/gfx/printsettings-service;1"]
        .getService(Components.interfaces.nsIPrintSettingsService);

        var printSettings = PSSVC.newPrintSettings;

        var file = profileDirectory();
        file.append(ps ? "fuzzout.ps" : "fuzzout.pdf");
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


function cycleCollect()
{
  return function cycleCollectInner() {
      try {
        content.QueryInterface(Ci.nsIInterfaceRequestor)
              .getInterface(Ci.nsIDOMWindowUtils)
              .cycleCollect();
      }

      catch(e) {
        dumpln("cycle collect failed " + e);
      }
  }
}


function fontList()
{
    return Components.classes["@mozilla.org/gfx/fontenumerator;1"]
            .createInstance(Components.interfaces.nsIFontEnumerator)
            .EnumerateAllFonts({})
            .join("\n");
}


function reftestList()
{
  var dir = extensionLocation().parent;
  dir.append("automation");
  return readFile(indir(dir, "urls-reftests"));
}


/**********************
 * FILESYSTEM HELPERS *
 **********************/

function profileDirectory()
{
  var fn = sendSyncMessage('DOMFuzzHelper.getProfileDirectory', {})[0];
  var d = Components.classes["@mozilla.org/file/local;1"]
                    .createInstance(Components.interfaces.nsILocalFile);
  d.initWithPath(fn);
  return d;
}

function extensionLocation()
{
  var d = profileDirectory();
  d.append("extensions");
  d.append("domfuzz@squarefree.com");

  var extensionLocation = readFile(d).replace(/\s*$/, "");

  var f = Components.classes["@mozilla.org/file/local;1"]
                    .createInstance(Components.interfaces.nsILocalFile);
  f.initWithPath(extensionLocation);
  return f;
}


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


function indir(dir, filename)
{
  var d = dir.clone();
  d.append(filename);
  return d;
}


/*************************
 * FUZZ SCRIPT INJECTION *
 *************************/


function maybeInjectScript(event)
{
  var doc = event.originalTarget;
  if (doc.nodeName != "#document")
    return;

  var hash = doc.location.hash;

  var r = hash.split(",");

  if (r[0] != "#squarefree-af") {
    return;
  }
  if (!(/^[a-zA-Z0-9\-.]*$/.test(r[1]))) {
    dump("Sketchy fuzzer filename!\n");
    return;
  }

  var dir = extensionLocation().parent;
  dir.append("fuzzers");

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

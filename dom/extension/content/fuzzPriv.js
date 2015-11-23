"use strict";

const Cu = Components.utils;
const Cc = Components.classes;
const Ci = Components.interfaces;

Cu.import("chrome://domfuzzhelper/content/file.jsm");

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

    // XXX This is probably insecure; check with bholley.
    window.wrappedJSObject.fuzzPriv = Cu.cloneInto(makeDOMFuzzHelper(window), window, {cloneFunctions: true});
  }
};

var domfuzzhelpermanager = new DOMFuzzHelperManager();


/*****************************
 * FUZZPRIV OBJECT INJECTION *
 *****************************/

function makeDOMFuzzHelper(aWindow) {
  dumpln("DOMFuzzHelper created");

  var helper = {
      toString: function() { return "[DOMFuzzHelper]"; },

      quitApplication: function() {
        dumpln("fuzzPriv.quitApplication");
        sendAsyncMessage('DOMFuzzHelper.quitApplication', {});
      },

      quitApplicationSoon: function() {
        dumpln("fuzzPriv.quitApplicationSoon");
        sendAsyncMessage('DOMFuzzHelper.quitApplicationSoon', {});
      },

      closeTabThenQuit: function () {
        // Somehow async messages get lost in close().
        sendSyncMessage('DOMFuzzHelper.quitApplicationSoon', {});

        // This frame-script stops running immediately after close().
        content.close();
      },

      quitWithLeakCheck: function () {
        sendAsyncMessage('DOMFuzzHelper.quitWithLeakCheck', {});
      },

      runSoon: runSoon.bind(this),

      // Garbage collection (those not covered by import of getJSTestingFunctions)
      GC:                         function() { Components.utils.getJSTestingFunctions().gc.apply(this, arguments); },
      forceShrinkingGC:           function() { Cu.forceShrinkingGC(); },
      schedulePreciseGC:          function() { Cu.schedulePreciseGC(function() { dumpln("precise GC complete"); }); },
      schedulePreciseShrinkingGC: function() { Cu.schedulePreciseShrinkingGC(function() { dumpln("precise shrinking GC complete"); }); },

      // Cycle collection
      CC:        cycleCollect(aWindow),
      CCLog:     cycleCollectLog(aWindow),
      forceGC:   function() { Cu.forceGC(); },
      finishCC:  function() { Cu.finishCC(); },
      ccSlice:   function(budget) { Cu.ccSlice(budget); },

      // Memory pressure
      MP: sendMemoryPressureNotification.bind(this),

      // Requests for information
      fontList: fontList.bind(this),
      reftestFilesDirectory: reftestFilesDirectory.bind(this),
      reftestList: reftestList.bind(this),
      cssPropertyDatabase: cssPropertyDatabase.bind(this),
      webidlDatabase: webidlDatabase.bind(this),
      comparePixels: comparePixels(aWindow),

      // Requests for things that Firefox or users do sometimes
      getMemoryReports: getMemoryReports.bind(this),
      printToFile: printToFile(aWindow),
      openAboutNewtab: function() { aWindow.open("about:newtab"); },
      resizeTo: safeResizeTo(aWindow),
      trustedKeyEvent: trustedKeyEvent(aWindow),
      callDrawWindow: callDrawWindow(aWindow),
      enableAccessibility: enableAccessibility.bind(this),
      zoom: setZoomLevel(aWindow),
  };

  var testingFunctions = Components.utils.getJSTestingFunctions();
  for (let key of Object.getOwnPropertyNames(testingFunctions)) {
    if (key.indexOf("SPSProfil") != -1) {
      // Bug 1005777
      continue;
    }
    if (!(key in helper)) {
      helper[key] = testingFunctions[key];
    }
  }

  return helper;
}


/***********************************************
 * MISC PRIVILEGED FUNCTIONS - CONTENT PROCESS *
 ***********************************************/

function trustedKeyEvent(window)
{
  return function(targetElement, type, ctrl, alt, shift, meta, keyCode, charCode) {
    // Check that window matches targetElement.ownerDocument? Nah.
    try {
      var event = targetElement.ownerDocument.createEvent("KeyboardEvent");
      event.initKeyEvent("key" + type, true, true, null, ctrl, alt, shift, meta, keyCode, charCode);
      targetElement.dispatchEvent(event);
    } catch(e) {
      dumpln("Error thrown while trying to make an event?");
      dumpln(e);
    }
  };
}



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
	dumpln("fuzzPriv.enableAccessibility");
        sendAsyncMessage('DOMFuzzHelper.enableAccessibility', {});
}

function sendMemoryPressureNotification()
{
  var os = Components.classes["@mozilla.org/observer-service;1"]
           .getService(Components.interfaces.nsIObserverService);
  os.notifyObservers(null, "memory-pressure", "heap-minimize");
}

function cycleCollect(window)
{
  return function cycleCollectInner(aExtraForgetSkippableCalls) {
    window.QueryInterface(Components.interfaces.nsIInterfaceRequestor)
          .getInterface(Components.interfaces.nsIDOMWindowUtils)
          .cycleCollect(null, aExtraForgetSkippableCalls);
  };
}

function cycleCollectLog(window)
{
  return function(allTraces, wantAfterProcessing, aExtraForgetSkippableCalls) {
    var logger = Components.classes["@mozilla.org/cycle-collector-logger;1"].createInstance(Components.interfaces.nsICycleCollectorListener);
    if (allTraces) {
      logger.allTraces();
    }
    logger.disableLog = true;
    logger.wantAfterProcessing = wantAfterProcessing;
    window.QueryInterface(Components.interfaces.nsIInterfaceRequestor).getInterface(Components.interfaces.nsIDOMWindowUtils).cycleCollect(logger, aExtraForgetSkippableCalls);
  };
}

function callDrawWindow(aWindow)
{
  // We allow the caller to specify a scale to match a drawWindow call that happens in stock Firefox:
  //   https://hg.mozilla.org/mozilla-central/annotate/6d7fae9764b3/browser/components/thumbnails/PageThumbs.jsm#l114
  // An alternative would be to allow the caller to pass in a canvas ctx (and then clear the ctx?).

  return function callDrawWindow2(flags, scale) {
    var w = aWindow.innerWidth;
    var h = aWindow.innerHeight;

    var canvas = aWindow.document.createElementNS("http://www.w3.org/1999/xhtml", "canvas");
    canvas.setAttribute("width", w);
    canvas.setAttribute("height", h);
    canvas.setAttribute("moz-opaque", "true");

    var ctx = canvas.getContext("2d");
    if (scale) {
      ctx.scale(scale, scale);
    }
    ctx.drawWindow(aWindow,
                   0,
                   0,
                   w,
                   h,
                   "rgb(255,255,255)",
                   +flags);
  };
}

function comparePixels(aWindow)
{
  return function comparePixels2() {
    var w = aWindow.innerWidth;
    var h = aWindow.innerHeight;
    dumpln(w + " x " + h);

    var canvas1 = aWindow.document.createElementNS("http://www.w3.org/1999/xhtml", "canvas");
    canvas1.setAttribute("width", w);
    canvas1.setAttribute("height", h);
    canvas1.setAttribute("moz-opaque", "true");

    var canvas2 = aWindow.document.createElementNS("http://www.w3.org/1999/xhtml", "canvas");
    canvas2.setAttribute("width", w);
    canvas2.setAttribute("height", h);
    canvas2.setAttribute("moz-opaque", "true");

    function drawInto(canvas)
    {
      var ctx = canvas.getContext("2d");
      ctx.drawWindow(aWindow,
                     aWindow.scrollX,
                     aWindow.scrollY,
                     w,
                     h,
                     "rgb(255,255,255)",
                     ctx.DRAWWINDOW_DRAW_CARET |
                     ctx.DRAWWINDOW_USE_WIDGET_LAYERS);
    }

    drawInto(canvas1);
    return function comparePixels3() {
      drawInto(canvas2);
      var wu = aWindow.QueryInterface(Ci.nsIInterfaceRequestor).getInterface(Ci.nsIDOMWindowUtils);
      var o = {};
      var n = wu.compareCanvases(canvas1, canvas2, o);
      if (n === 0) { return ""; }
      return (
        n + " pixel" + (n == 1 ? "" : "s") + " differ (max channel difference: " + o.value + ")\n" +
        "Before:\n" + canvas1.toDataURL() + "\n" +
        "After:\n" + canvas2.toDataURL() + "\n"
      );
    };
  };
}

function setZoomLevel(window)
{
  return function setZoomLevelInner(textOrFull, factor) {
    var viewer = window.QueryInterface(Components.interfaces.nsIInterfaceRequestor)
                       .getInterface(Components.interfaces.nsIWebNavigation)
                       .QueryInterface(Components.interfaces.nsIDocShell)
                       .contentViewer

    if (textOrFull == "text")
      viewer.textZoom = +factor;
    else if (textOrFull == "full")
      viewer.fullZoom = +factor;
  }
}

function safeResizeTo(aWindow)
{
  function clamp(a, b, c)
  {
    return Math.min(c, Math.max(a, b));
  }

  return function(w, h) {
    w = clamp(200, w, aWindow.screen.width);
    h = clamp(200, h, aWindow.screen.height);
    aWindow.resizeTo(w, h);
  };
}


function printToFile(window)
{
  // Disabled completely for now.
  return function() { };

  // Oddly asynchronous, at least on Linux.

  // Linux: works for PDF and PS.
  // Windows: works for PDF at least. Text may be invisible (bug 653336). showHeaders causes an abnormal exit. Fairly busted and unlikely to be fixed as a result of me filing bugs.
  // Mac: tested, printToFile is ignored and it goes to a printer! (bug 675709)
  var xulRuntime = Components.classes["@mozilla.org/xre/app-info;1"]
                             .getService(Components.interfaces.nsIXULRuntime);
  if (xulRuntime.OS != "Linux") return function() { };

  var fired = false;

  return function printToFileInner(showHeaders, showBGColor, showBGImages, ps) {
    runSoon(function() {
        // Don't print more than once, it gets messy fast.
        if (fired) { return false; }
        fired = true;

        ps = ps && xulRuntime.OS != "WINNT"; // Windows gets confused when trying to print to ps, and tosses up a *.xps filepicker outside the Firefox process!?

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
  };
}


function getMemoryReports(anonymize)
{
  // This is one of the things that happens when you use the "Measure" button on about:memory
  // (about:memory does a bunch of post-processing, including assertions about nonnegative numbers)
  var mrm = Cc["@mozilla.org/memory-reporter-manager;1"].getService(Ci.nsIMemoryReporterManager);
  mrm.getReports(function(){}, null, function(){}, null, !!anonymize);
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

function webidlDatabase()
{
  var dir = extensionLocation().parent;
  dir.append("webidl");
  return readFile(indir(dir, "webidl.json"));
}

function cssPropertyDatabase()
{
  var f = fileObject(reftestFilesDirectory());
  f.append("layout");
  f.append("style");
  f.append("test");
  f.append("property_database.js");
  return readFile(f);
}


function reftestFilesDirectory()
{
  return getEnv("REFTEST_FILES_DIR");
}

function profileDirectory()
{
  var fn = sendSyncMessage('DOMFuzzHelper.getProfileDirectory', {})[0];
  var d = fileObject(fn);
  return d;
}

function extensionLocation()
{
  var d = profileDirectory();
  d.append("extensions");
  d.append("domfuzz@squarefree.com");

  var loc = readFile(d).replace(/\s*$/, "");
  return fileObject(loc);
}

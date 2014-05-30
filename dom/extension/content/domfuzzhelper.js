"use strict";

// Separate scope to work around bug 673569
(function() {

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

    // "DOMWindowCreated" is too early to inject <script> elements (there is no document.documentElement)
    // "load" is too late to trigger some bugs (see bug 790252 comment 5)
    window.addEventListener("DOMContentLoaded", maybeInjectScript, false);
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
        // Somehow async messages get lost in close().
        sendSyncMessage('DOMFuzzHelper.quitApplicationSoon', {});

        // This frame-script stops running immediately after close().
        content.close();
      },

      quitWithLeakCheck: function () {
        sendAsyncMessage('DOMFuzzHelper.quitWithLeakCheck', {});
      },

      runSoon: runSoon.bind(this),

      enableAccessibility: enableAccessibility.bind(this),

      forceGC: function() { Cu.forceGC(); },

      CC: cycleCollect(aWindow),
      finishCC: function() { Cu.finishCC(); },
      ccSlice: function(budget) { Cu.ccSlice(budget); },

      CCLog: cycleCollectLog(aWindow),

      MP: sendMemoryPressureNotification.bind(this),

      // Using the apply/arguments pattern because some of these functions (GC, gcslice) vary their behavior based on the number of arguments
      // XXX can I somehow change this to be just a list of functions that we allow to be forwarded?
      GC:                                    function() { Components.utils.getJSTestingFunctions().gc.apply(this, arguments); },
      gc:                                    function() { Components.utils.getJSTestingFunctions().gc.apply(this, arguments); },
      deterministicgc:                       function() { Components.utils.getJSTestingFunctions().deterministicgc.apply(this, arguments); },
      schedulegc:                            function() { Components.utils.getJSTestingFunctions().schedulegc.apply(this, arguments); },
      selectforgc:                           function() { Components.utils.getJSTestingFunctions().selectforgc.apply(this, arguments); },
      gczeal:                                function() { Components.utils.getJSTestingFunctions().gczeal.apply(this, arguments); },
      gcslice:                               function() { Components.utils.getJSTestingFunctions().gcslice.apply(this, arguments); },
      setIonCheckGraphCoherency:             function() { Components.utils.getJSTestingFunctions().setIonCheckGraphCoherency.apply(this, arguments); },
      enableOsiPointRegisterChecks:          function() { Components.utils.getJSTestingFunctions().enableOsiPointRegisterChecks.apply(this, arguments); },
      gcPreserveCode:                        function() { Components.utils.getJSTestingFunctions().gcPreserveCode.apply(this, arguments); },
      minorgc:                               function() { Components.utils.getJSTestingFunctions().minorgc.apply(this, arguments); },
      gcparam:                               function() { return Components.utils.getJSTestingFunctions().gcparam.apply(this, arguments); },
      countHeap:                             function() { return Components.utils.getJSTestingFunctions().countHeap.apply(this, arguments); },
      setJitCompilerOption:                  function() { Components.utils.getJSTestingFunctions().setJitCompilerOption.apply(this, arguments); },
      // Disabled: bug 1005777
      //enableSPSProfiling:                    function() { Components.utils.getJSTestingFunctions().enableSPSProfiling.apply(this, arguments); },
      //enableSPSProfilingWithSlowAssertions:  function() { Components.utils.getJSTestingFunctions().enableSPSProfilingWithSlowAssertions().apply(this, arguments); },
      //disableSPSProfiling:                   function() { Components.utils.getJSTestingFunctions().disableSPSProfiling.apply(this, arguments); },

      verifyprebarriers:            function() { Components.utils.getJSTestingFunctions().verifyprebarriers(); },
      verifypostbarriers:           function() { Components.utils.getJSTestingFunctions().verifypostbarriers(); },
      terminate:                    function() { Components.utils.getJSTestingFunctions().terminate(); },

      forceShrinkingGC: function() { Cu.forceShrinkingGC(); },

      schedulePreciseGC: function() { Cu.schedulePreciseGC(function() { dumpln("precise GC complete"); }); },

      schedulePreciseShrinkingGC: function() { Cu.schedulePreciseShrinkingGC(function() { dumpln("precise shrinking GC complete"); }); },

      fontList: fontList.bind(this),
      reftestFilesDirectory: reftestFilesDirectory.bind(this),
      reftestList: reftestList.bind(this),
      cssPropertyDatabase: cssPropertyDatabase.bind(this),
      webidlDatabase: webidlDatabase.bind(this),

      printToFile: printToFile(aWindow),

      openAboutMemory: function(compartments, verbose) {
        aWindow.open((compartments ? "about:compartments" : "about:memory") + (verbose ? "?verbose" : ""));
      },

      openAboutNewtab: function() { aWindow.open("about:newtab"); },


      comparePixels: comparePixels(aWindow),

      callDrawWindow: callDrawWindow(aWindow),

      resizeTo: safeResizeTo(aWindow),

      trustedKeyEvent: trustedKeyEvent(aWindow),

      __exposedProps__: {
        'toString': 'r',
        'quitApplication': 'r',
        'quitApplicationSoon': 'r',
        'closeTabThenQuit': 'r',
        'quitWithLeakCheck': 'r',
        'runSoon': 'r',
        'enableAccessibility': 'r',
        'forceGC': 'r',
        'GC': 'r',
        'gc': 'r',
        'CC': 'r',
        'CCLog': 'r',
        'finishCC': 'r',
        'ccSlice': 'r',
        'MP': 'r',
        'forceShrinkingGC': 'r',
        'schedulePreciseGC': 'r',
        'schedulePreciseShrinkingGC': 'r',
        'fontList': 'r',
        'printToFile': 'r',
        'openAboutMemory': 'r',
        'openAboutNewtab': 'r',
        'reftestList': 'r',
        'cssPropertyDatabase': 'r',
        'webidlDatabase': 'r',
        'comparePixels': 'r',
        'callDrawWindow': 'r',
        'resizeTo': 'r',
        deterministicgc: 'r',
        schedulegc: 'r',
        selectforgc: 'r',
        gczeal: 'r',
        gcslice: 'r',
        gcparam: 'r',
        countHeap: 'r',
        verifyprebarriers: 'r',
        verifypostbarriers: 'r',
        terminate: 'r',
        reftestFilesDirectory: 'r',
        trustedKeyEvent: 'r',
        setIonCheckGraphCoherency: 'r',
        enableOsiPointRegisterChecks: 'r',
        gcPreserveCode: 'r',
        minorgc: 'r',
        setJitCompilerOption: 'r',
        // Disabled: bug 1005777
        //enableSPSProfiling: 'r',
        //enableSPSProfilingWithSlowAssertions: 'r',
        //disableSPSProfiling: 'r',
      }
  };
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
  //   http://hg.mozilla.org/mozilla-central/annotate/6d7fae9764b3/browser/components/thumbnails/PageThumbs.jsm#l114
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


/**********************
 * FILESYSTEM HELPERS *
 **********************/

function getEnv(key)
{
  var env = Components.classes["@mozilla.org/process/environment;1"]
                      .getService(Components.interfaces.nsIEnvironment);
  return env.get(key);
}

function fileObject(path)
{
  var f = Components.classes["@mozilla.org/file/local;1"]
                    .createInstance(Components.interfaces.nsILocalFile);
  f.initWithPath(path);
  return f;
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
  if (doc.nodeName != "#document") {
    return;
  }

  if (doc.location === null) {
    // Some weird situation with iframes and document.write and navigation can trigger this.
    return;
  }

  var hash = doc.location.hash;
  if (!hash.startsWith("#fuzz=")) {
    return;
  }

  var fuzzSettings = hash.slice(6).split(",").map(function(s) { return parseInt(s); });

  var domFuzzerScript = getEnv("DOM_FUZZER_SCRIPT");
  if (!domFuzzerScript) {
    return;
  }

  var scriptToInject =
    (readFile(fileObject(domFuzzerScript)) + "\n"
  + "document.getElementById('fuzz1').parentNode.removeChild(document.getElementById('fuzz1'));\n"
  + "fuzzSettings = [" + fuzzSettings.join(",") + "];\n"
  + "fuzzOnload();\n");

  var insertionPoint = doc.getElementsByTagName("head")[0] || doc.documentElement;
  if (!insertionPoint) {
    return;
  }

  var script = doc.createElementNS("http://www.w3.org/1999/xhtml", "script");
  script.setAttribute("id", "fuzz1");
  script.setAttribute("type", "text/javascript;version=1.7");
  script.textContent = scriptToInject;
  insertionPoint.appendChild(script);
}

})();

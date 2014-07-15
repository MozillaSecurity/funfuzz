"use strict";

// Separate scope to work around bug 673569
(function() {

const Cu = Components.utils;
const Cc = Components.classes;
const Ci = Components.interfaces;

Cu.import("chrome://domfuzzhelper/content/file.jsm"); // How does this interact with the scope created to work around bug 673569??

// content script for e10s support

// This is a frame script, so it may be running in a content process.
// In any event, it is targeted at a specific "tab", so we listen for
// the DOMWindowCreated event to be notified about content windows
// being created in this context.

function DOMFuzzInjector() {
  addEventListener("DOMWindowCreated", this, false);
}

DOMFuzzInjector.prototype = {
  handleEvent: function handleEvent(aEvent) {
    var window = aEvent.target.defaultView;

    // "DOMWindowCreated" is too early to inject <script> elements (there is no document.documentElement)
    // "load" is too late to trigger some bugs (see bug 790252 comment 5)
    window.addEventListener("DOMContentLoaded", maybeInjectScript, false);
  }
};

var injector = new DOMFuzzInjector();


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
  injectScript(doc, fuzzSettings);
}


function injectScript(doc, fuzzSettings)
{
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

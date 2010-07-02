Components.utils.import("resource://gre/modules/XPCOMUtils.jsm");

// Based on:
// https://bugzilla.mozilla.org/show_bug.cgi?id=549539
// https://bug549539.bugzilla.mozilla.org/attachment.cgi?id=429661
// https://developer.mozilla.org/en/XPCOM/XPCOM_changes_in_Gecko_1.9.3
// http://mxr.mozilla.org/mozilla-central/source/toolkit/components/console/hudservice/HUDService.jsm#3240
// https://developer.mozilla.org/en/how_to_build_an_xpcom_component_in_javascript

`

const Cc = Components.classes;
const Ci = Components.interfaces;

dump("YAY\n");

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
      //dump("p-a-c\n");
      this.init();
    } else if (aTopic == "content-document-global-created") {
      //dump("global-created\n");
      aSubject.wrappedJSObject.fuzzFoo = function() { dump('fuzzFoo called\n'); }
    } else if (aTopic == "xpcom-shutdown") {
      //dump("shutdown\n");
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

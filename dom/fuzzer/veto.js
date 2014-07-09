/*

 Input blacklists for minor symptoms:

 * Hangs
 * Leaks
 * Inconsistent rendering

*/

var fuzzBlacklistVeto = function() { return false; };
function fuzzInitBlacklists()
{
    var blacklists = [
        {
            magicString: "hang",
            list: [
                "selfdestruct",
                "rel=\"stylesheet",  // paranoia of inclusion
                ".js\"",             // paranoia of inclusion
                "fuzzRepeat",        // can create exponential blowup, e.g. with cloneNode + appendChild
                "array",             // fuzzerRandomJS can accidentally create gigantic arrays
                "gczeal",            // slow
                "\"length",          // bug 346268, fuzzerRandomJS hang
                "fuzzerRandomJS",    // Gigantic arrays, destructiveAndAnnoying
                "uneval",            // Gigantic arrays are sadmaking
                "frame",             // setting src can toss up a dialog (bug 331334)
                "iframe",            // setting src can toss up a dialog (bug 331334)
                "ftp:",              // bug 250098 (modal dialog interpreted as a hang)
                "beforeunload",      // dialog on attempt to quit
                "defineProperty",    // can accidentally create multiple-infinite-recursion
                "defineSetter",      // can accidentally create multiple-infinite-recursion
                "defineGetter",      // can accidentally create multiple-infinite-recursion
                "onerror",           // can get itself into infinite loops if it triggers async errors
                "cloneNode",         // can create exponentially many nodes
                "KEEPLISTENER",      // mutation events can loop/nest infinitely
                "OMGback",           // bfcache is reliable, as explained where OMGback lives
                "float",             // bug 460705, bug 493910
                "collapse",          // bug 513106
                "-moz-border",       // bug 543648
                "MozBorder",         // bug 543648
                "execCommand",       // bug 543651
                "MathML",            // bug 544453
                "repeating-radial-gradient", // bug 557348
                "repeating-linear-gradient",
                "radial-gradient",
                "stroke-width",      // bug 564889
                "strokeWidth",       // bug 564889
                "letter-spacing",    // can be slow
                "letterSpacing",     // can be slow
                "autoplay",          // bug 573426 (windows only)
                "shadow",            // bug 595042
                "filter",            // bug 612213
                "title",             // rdar://8706039
                "window.open",       // bug 622218
                "showModalDialog",   // bug 622218?
                "position",          // bug 622314
                "break-word",        // bug 628358
                "padding",           // bug 628358
                "-moz-grid",         // bug 628358
                "<table",            // :(
                "onload",            // bug 693725
                "click",             // bug 762566
                "trustedKeyEvent",   // can navigate away (?)
                "__proto__",         // bug 801914 (too-much-recursion stops the fuzzer, which is interpreted by the python harness as a hang)
                "202E",              // bug 812826 (RLO causes a hang in CoreText)
                "MediaSource",       // bug 931388
                "notification",      // general badness when spammed (bug 897367, bug 866653)
                "generateCRMFRequest", // bug 922034 (master password dialog, especially when it interferes with quitting)
                "strokeText",        // bug 943622
                "strokeRect",        // bug 986902
                ".arc",              // bug 943587
                "isPointInStroke",   // bug 989669
                "scale",             // bug 1017942
                "quadraticCurveTo",  // bug 1017942
                "location.reload",   // accidentally reloading the main testcase would cancel the quit timer
                "-moz-column",       // bug 1007312
                "VTTCue",            // bug 1010707
                "addCue",            // bug 1010707
                "addTextTrack",      // bug 1010707
                "rowspan",           // slow enough to "hang" a debug build, but not an opt build
                "OfflineAudioContext", // bug 1032656
            ]
        },
        {
            magicString: "leak",
            list: [
                "rel=\"stylesheet",  // paranoia of inclusion
                ".js\"",             // paranoia of inclusion
                "fuzzPriv.printToFile", // printing is asynchronous, and shutting down while printing can leak
                "view-source",       // bug 700768
                "contentEditable",   // bug 718282, bug 771431
                "designMode",        // bug 718282?
                "execCommand",       // bug 718282?
                "atom",              // bug 397206
                "rss",               // bug 397206
                "mask",              // bug 728632
                "clip",              // bug 728632
                "filter",            // bug 728632
                "xlink",             // bug 728632
                "applet",            // bug 728933
                "spampede",          // bug 728933
                "265986",            // bug 728933
                "328751",            // bug 728933
                "99776",             // bug 728933
                "getUserMedia",      // bug 826538
                "@import",           // bug 842309
                "undoManager",       // bug 851638
                "webgl",             // bug 859542
                "history",           // bug 860482
                "frame",             // bug 860482
                "object ",           // bug 860482
                "object>",           // bug 860482
                "object'",           // bug 860482
                "object\"",          // bug 860482
                "trustedKeyEvent",   // leak with search bar (bug 867290)
                "window.open",       // bug 867307
                "@media",            // bug 884212
                "/*charCode*/73",    // leak with page info (bug 829831)
                "/*charCode*/105",   // leak with page info (bug 829831)
                "/*keyCode*/118",    // leak with style editor (bug 865027)
                "notification",      // general badness when spamming Notifications (bug 897367, bug 866653)
                "\\u",               // bug 963878
                "Worker",            // annoying timing-dependent leaks
                "rowspan",           // annoying timing-dependent leaks
                "color",             // bug 991373
                "insertItemBefore",  // bug 1015551
                "generateCRMFRequest", // dialog does weird things to shutdown sequence
                "animVal",           // bug 1033301
                "TrackEvent",        // bug 1035654
            ]
        },
        {
            magicString: "render inconsistently",
            list: [
                "nearNativeStackLimit", // kinda expected to break things
                "nearScriptStackLimit", // kinda expected to break things
                "iframe",           // bug 254144 - paints white immediately after a move
                "frameset",         // ditto
                "object ",          // can act like an iframe
                "object>",          // can act like an iframe
                "object'",          // can act like an iframe
                "object\"",         // can act like an iframe
                "embed",            // animated infobar + async missing-plugin box
                "applet",           // animated infobar + async missing-plugin box
                "spampede",         // animated infobar + async missing-plugin box
                "img",              // async loading
                "image",            // async loading; bug 409494
                "@font-face",       // async loading
                "select",           // bug 393325; internal scrolling; general weirdness
                "button",           // bug 393325 (mac and linux)
                "input",            // bug 393325 (mac and linux)
                "canvas",           // changing a canvas's width can undraw things, which makes sense
                "textarea",         // non-empty textareas can trigger spellcheck :(
                "contenteditable",  // carets, selections, etc.
                "getSelection",     // can be used to select text, which changes its background
                "find",             // selects text
                "scrollto",         // a page that changes the scroll position will just confuse us
                "scrollby",         // ditto
                "scrollIntoView",   // ditto
                "location.hash",    // ditto
                "trustedKeyEvent",  // ditto
                "deleteRule",       // CSS DOM, modifying a stylesheet
                "insertRule",       // CSS DOM, modifying a stylesheet
                "url",              // CSS background images that might load slowly
                "background=",      // HTML background images that might load slowly
                ":first-letter",    // bug 145419 :(
                ":first-line",      // bug 145419
                "border-collapse",  // bug 203686
                "@import",          // async even for data: URLs?
                ".disabled",        // stylesheet enablement is recomputed when <link> is readded to document, per #whatwg
                ":hover",           // cursor checking is intentionally weird
                "marquee",          // animation (marquee)
                "animfish.gif",     // animation (GIF)
                "transition",       // animation
                "animate",          // animation (SMIL)
                "smil-util.js",     // animation (SMIL)
                "progress",         // animation
                "<set",             // animation (SVG)
                "\"set",            // animation (SVG)
                "focus",            // disappearing focus rings; scrolling into view
                "select()",         // disappearing focus rings; scrolling into view
                '["select"]',       // disappearing focus rings; scrolling into view
                "selectionStart",   // disappearing selections - <input type="text">
                "selectionEnd",     // disappearing selections - <input type="text">
                "setSelectionRange",// disappearing selections - <input type="text">
                "selected",         // disappearing selections - <select>
                "video",            // async and animated
                "audio",            // async and animated (loading/seekbar)
                "cssrules",         // Modifications to stylesheets aren't reflected in the DOM node tree, so a bounce blows them away.
                "colgroup",         // bug 551239
                "table-caption",    // bug 501035
                "table-footer",     // bug 501035?
                "table-header",     // bug 501035?
                "table-column",     // bug 501035?
                "text-indent",      // bug 718157
                "textIndent",       // bug 718157
                "-moz-grid",        // bug 521600
                "-moz-inline-grid", // bug 521600
                "rules",            // bug 543791
                "overflow",         // bug 718037, bug 718123
                "-moz-box",         // bug 718211, bug 726548
                "-moz-deck",        // bug 718211, bug 726548
                "-moz-stack",       // bug 718211, bug 726548
                "-moz-inline-stack",// bug 718211, bug 726548
                "-moz-inline-grid", // bug 718211, bug 726548
                "-moz-inline-box",  // bug 718211, bug 726548
                "-moz-column",      // bug 718331
                "MozColumn",        // bug 718331
                "-moz-border",      // bug 718452
                "MozBorder",        // bug 718452
                "-moz-padding",     // bug 718452
                "MozPadding",       // bug 718452
                "-moz-appearance",  // something weird happens on linux
                "MozAppearance",    // something weird happens on linux
                "skew",             // bug 720077
                "opacity",          // bug 720078
                "<li",              // bug 721027
                "\"li",             // bug 721027
                "list-item",        // bug 721027
                "svg",              // the combination of bug 723376 and bug 475216
                "float",            // bug 725928 :(
                "relative",         // bug 728100 :(
                "absolute",         // bug 728100 :(
                "&shy",             // bug 732740, bug 767279
                "00AD",             // bug 732740, bug 767279
                "xAD",              // bug 732740, bug 767279
                "hyphen",           // bug 732740, bug 767279
                "perspectiveOrigin",   // bug 752779
                "perspective-origin",  // bug 752779
                "padding",          // bug 763560, bug 764256
                "border",           // bug 763560
                "transform-style",  // bug 767233
                "transformStyle",   // bug 767233

                // Mutation events might be triggered by the test itself
                "DOMSubtreeModified",
                "DOMNodeInserted",
                "DOMNodeRemoved",
                "DOMNodeRemovedFromDocument",
                "DOMNodeInsertedIntoDocument",
                "DOMAttrModified",
                "DOMCharacterDataModified",

                // Other events (etc) that might be triggered by the test itself
                "MozScrolledAreaChanged",
                "mozRequestFullScreen",
            ]
        }
    ];

    if (navigator.userAgent.indexOf("Mac OS X 10.7;") != -1) {
        blacklists[0].list.push("unicode-bidi"); // bug 849987
    }

    var HANG_TOO_LONG = 5000;

    var xml = document.documentElement ? (new XMLSerializer()).serializeToString(document.documentElement).toLowerCase() : "";

    function shouldEnableBlacklist(list, magicString)
    {
        // This must be first, so the advancement of the RNG is deterministic.
        var usually = rnd(4);

        // Fennec - we don't understand multiprocess leak logs yet.
        if (magicString == "leak" && navigator.userAgent.indexOf("Fennec") != -1)
            return false;

        // Fennec - blah
        if (magicString == "hang" && navigator.userAgent.indexOf("Fennec") != -1)
            return false;

        for (var i = 0; i < list.length; ++i) {
            var blacklistEntry = list[i];
            // First, determine whether the document contains the blacklisted text.
            var blacklistEntryLower = blacklistEntry.toLowerCase();
            if (xml.indexOf(blacklistEntryLower) != -1) {
                dumpln("May " + magicString + " due to known troublemaker \"" + blacklistEntry + "\".");
                return false;
            }

            // Second, determine whether recorded fuzz commands contain the blacklisted text.
            if (fuzzCommands) {
                for (var j = 0; j < fuzzCommands.length; ++j) {
                    var fun = fuzzCommands[j].fun;
                    if (fun && typeof fun.toString == "function") {
                        var fs = fun.toString();
                        if (fs.length > HANG_TOO_LONG && magicString == "hang")
                            return false;
                        if (fs.toLowerCase().indexOf(blacklistEntryLower) != -1) {
                            dumpln("May " + magicString + " due to fuzzCommands[" + j + "] matching known troublemaker \"" + blacklistEntry + "\".");
                            return false;
                        }
                    }
                }
            }
        }

        // Usually (but randomly) disable the blacklist, so we can at least test all web features for crashes and assertions.
        // This must be last, so the "May..." lines always get printed.
        if (usually && !fuzzCommands) {
            return false;
        }

        return true;
    }

    for (var blacklist, j = 0; (blacklist = blacklists[j]); ++j) {
        blacklist.enabled = shouldEnableBlacklist(blacklist.list, blacklist.magicString);
        if (blacklist.enabled) {
            dumpln("Not expected to " + blacklist.magicString); // MAGIC STRING that rundomfuzz.py looks for.
        } else {
            dumpln("Allowed to " + blacklist.magicString);
        }
    }

    fuzzBlacklistVeto = function fuzzBlacklistVeto(s)
    {
        for (var blacklist, j = 0; (blacklist = blacklists[j]); ++j) {
            if (!blacklist.enabled)
                continue;
            if (blacklist.magicString == "hang" && s.length > HANG_TOO_LONG) {
                dumpln("Veto: too long.");
                return true;
            }
            var list = blacklist.list;
            for (var i = 0; i < list.length; ++i) {
                var blacklistEntry = list[i];
                var blacklistEntryLower = blacklistEntry.toLowerCase();
                if (s.toLowerCase().indexOf(blacklistEntryLower) != -1) {
                    dumpln("Veto: " + blacklistEntry + " matched " + s);
                    return true;
                }
            }
        }
        return false;
    };
}

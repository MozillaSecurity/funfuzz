// for fuzz.js
var fuzzerName = "DOMFuzz";
var recordStrategy = "Record as it goes";
var suggestedMaxSteps = 3000;

var fuzzRegisteredModules = [];
var fuzzActiveModules = [];

// Each fuzzer module file will call registerModule
function registerModule(name, weight)
{
  fuzzRegisteredModules.push({v: name, w: weight});
}

function chooseModules()
{
  var numFuzzers = rnd(5) + 1;

  var randomModule = Random.weighted(fuzzRegisteredModules);

  for (var i = 0; i < numFuzzers; ++i)
    fuzzActiveModules.push(Random.index(randomModule));

  dumpln("Chosen fuzzer(s): " + fuzzActiveModules.join(", "));
  fuzzerName += " [" + fuzzActiveModules.join(", ") + "]"; // !!!
}

function initFuzzerSpecific()
{
  chooseModules();
  fuzzInitBlacklists();
  Things.init();
  startFuzzing(fuzzKickoff);
}

function fuzzKickoff()
{
  if (o.length > 10000) {
    dumpln("This document contains so many nodes that reduction would be painful and serializeDOMAsScript might hang!");
    fuzzPriv.quitApplication();
    throw 3;
  }
  fuzzAddInitialNodes();
  serializeDOMAsScript();
}

function fuzzAddInitialNodes()
{
  var fuzzRoot = document.documentElement;
  if (fuzzRoot) {
    addDOMNodes(fuzzRoot, false, false, false);
  } else {
    try {
      o.push(document.createElementNS("http://www.w3.org/1999/xhtml", "div"));
    } catch(e) {
      o.push(null);
    }
  }
}


function makeCommand()
{
  var moduleName = Random.index(fuzzActiveModules);
  var module = window[moduleName];
  if (!module) { throw "Missing module: " + moduleName; }
  var s = module.makeCommand();

  if (typeof(s) == "string") {
    if (fuzzBlacklistVeto(s))
      return [];
  } else if (typeof(s) == "object") {
    for (var i = 0; i < s.length; ++i)
      if (fuzzBlacklistVeto(s[i]))
        return [];
  } else {
    return "/* OMG WTF " + moduleName + " */";
  }
  return s;
}


var fuzzSubCommand = (function() {
  var recursionCount = 0;

  function rawSub()
  {
    var subCommand = "";
    var iters = 0;
    while (subCommand.length === 0 && ++iters < 10)
      subCommand = makeCommand();
    if (typeof subCommand == "object")
      subCommand = subCommand.join(" ");
    return subCommand;
  }

  return function fuzzSubCommand(hint)
  {
    ++recursionCount;

    var subCommand = "";

    if (recursionCount < 3) {
      while (rnd(2)) {
        subCommand += "try { " + rawSub() + " } catch(esub) { } ";
      }
    }

    if (recursionCount < 4) {
      subCommand += rawSub();
    }

    if (subCommand.length !== 0 && hint) {
      var longHint = "[[" + hint + "[" + window.immedCount + "." + (10 + rnd(90)) + "]\n";
      if (self.dump) {
        subCommand = "dump(\"[[\" + " + simpleSource(longHint) + "); " +
          subCommand +
          " dump(\"]]]]\\n\");";
      }
    }

    --recursionCount;

    return subCommand;
  };
})();

var fuzzerWebIDL = (function () {

  var db = null;
  var interfaces = [];
  var favoriteTweakers = [];

  function ensureDB()
  {
    if (!db) {
      db = JSON.parse(fuzzPriv.webidlDatabase());
      for (var name in db) {
        if (db[name].type == "interface" && name in self) {
          interfaces.push(name);
        }
      }
    }
  }

  function gimmea(name)
  {
    if (rnd(200) === 0) {
      return Things.any() + " /*messin*/";
    }

    switch(name) {
      case "any":
        return whatever();
      case "boolean":
        return rnd(2) ? "true" : "false";
      case "short":
      case "unsigned short":
      case "long":
      case "unsigned long":
      case "long long":
      case "unsigned long long":
      case "DOMTimeStamp":
        return fuzzValues.jsNumbers();
      case "float":
      case "double":
      case "unrestricted double":
      case "unrestricted float":
         return fuzzValues.jsNumbers();
      case "DOMString":
      case "ByteString": // https://heycam.github.io/webidl/#idl-ByteString
      case "USVString": // https://heycam.github.io/webidl/#idl-USVString
        return simpleSource(Random.pick([fuzzValues.texts, fuzzValues.URIs]));
      case "WindowProxy":
        return Things.instance("Window");
      default:
    }

    if (!(name in db)) {
      if (!(name in self)) {
        return whatever() + " /* no webidl info or found interface for: " + name + "*/";
      }
      return Things.instance(name); // appropriate for e.g. Int32Array
    }
    var item = db[name];

    var note = " /* " + name + " (" + item.type + ") */";
    switch(item.type) {
      case "callback": return whateverFunction() + note;
      case "callback interface": return whatever() + note; // XXX make a matching object!
      case "dictionary": return genDictionary(name) + note;
      case "enum": return simpleSource(Random.index(item.values)) + note;
      case "typedef": return gimmei(item.idlType) + note;
      case "interface": return (rnd(10) ? Things.instance(name) : null) + note;
      default: return "/* whaaaat */" + note;
    }
  }

  // Call this with objects that look like { union: ..., array: ... }
  function gimmei(k) {
    if (rnd(200) === 0) {
      return Things.any() + " /*messing*/";
    }

    if (k.union) {
      return gimmei(Random.index(k.idlType));
    }
    if (k.array || k.sequence) {
      return "[" + several(function(){return gimmei(k.idlType);}).join(", ") + "]" + "/*idl_seq*/";
    }
    if (typeof k.idlType == "string") {
      return gimmea(k.idlType);
    }
    dumpln(uneval(k));
    return Things.any() + "/* whuck */";
  }

  function genDictionary(name)
  {
    var s = "{ ";
    var fill = rnd(4); // 0 = omit all fields, 3 = include all fields
    var maybeComma = "";

    while (name) {
      //s += "/* members of dictionary " + name + ": */ "
      var item = db[name];
      for (var i = 0; (member = item.members[i]); ++i) {
        if (member.required ? (rnd(100) > 0) : (rnd(3) < fill)) {
          s += maybeComma + genDictionaryMember(simpleSource(member.name), gimmei(member.idlType));
          maybeComma = ", ";
        }
      }
      name = item.inheritance;
    }

    s += " }";
    return s;
  }

  function genDictionaryMember(quotedName, value)
  {
    if (rnd(5)) {
      return quotedName + ": " + value;
    } else {
      return "get " + quotedName + "() { " + fuzzSubCommand("dictget") + "return " + value + "; }";
    }
  }

  function several(f)
  {
    var a = [];
    while (rnd(3))
      a.push(f());
    return a;
  }

  function whatever() {
    return rnd(10) ? Things.any() : "null";
  }

  function whateverFunction() {
    return Things.anyFunction();
  }

  function construct(ifaceName)
  {
    var iface = db[ifaceName];
    var constructors = [];
    for (var a of iface.extAttrs) {
      if (a.name == "Constructor") {
        constructors.push(a);
      }
    }
    if (constructors.length === 0) {
      return "/* no webidl constructor for " + ifaceName + " */";
    }
    if (ifaceName == "OfflineAudioContext" && rnd(20)) {
      return "/*hangy*/";
    }
    dumpln("Constructing: " + ifaceName);
    var maybeWindow = rnd(5) ? "" : "." + Things.instance("Window");
    return Things.reserve() + " = " + (rnd(10) ? "new " : "") + ifaceName + "(" + argumentList(Random.index(constructors).arguments) + ")" + ";";
  }

  function createInstanceTweaker(ifaceName, instance, reasonable)
  {
    var iface = db[ifaceName];
    var members = allMembers(iface);
    // dumpln(ifaceName + ": " + uneval(members));
    if (members.length === 0) {
      return "/* no members on " + ifaceName + " */";
    }

    return function() {
      var member = Random.index(members);
      if (!member.name) {
        // e.g. with "setter": true
        return "/* " + ifaceName + " has a weird member */";
      }

      if (propertyIsAnnoying(eval(instance), member.name) && rnd(100)) {
        return "/* the property " + member.name + " on our " + ifaceName + " is considered annoying */";
      }

      var memberExpr = instance + "[" + simpleSource(member.name) + "]";
      if (member.type == "attribute") {
        if (rnd(2)) {
          return "fuzzerWebIDL.rv = " + memberExpr + ";";
        } else {
          var prefix = reasonable ? "" : "fuzzInternalErrorsAreBugs = false; "; // We might be overwriting something important on |window|
          return prefix + memberExpr + " = " + gimmei(member.idlType) + ";";
        }
      }
      if (member.type == "operation") {
        return "fuzzerWebIDL.rv = " + (memberExpr + "(" + argumentList(member.arguments) + ")") + ";";
      }
      if (member.type == "const") {
        return memberExpr + ";";
      }
      return "/* bwuh? " + member.type + " */";
    };
  }

  function argumentList(args)
  {
    if (!args) {
      // e.g. AudioContext's first constructor
      return "";
    }
    var s = "";
    for (var i = 0; i < args.length; ++i) {
      var arg = args[i];
      if (arg.optional && rnd(10) === 0) {
        break;
      }
      if (s.length > 0) {
        s += ", ";
      }
      s += "/*" + arg.name + "*/ " + gimmei(arg.idlType);
      if (arg.variadic && rnd(2)) {
        --i;
      }
    }
    return s;
  }

  function allMembers(iface)
  {
    var members = [];
    members = members.concat(iface.members);
    if (iface.inheritance) {
      members = members.concat(allMembers(db[iface.inheritance]));
    }
    if (iface.implements) {
      for (var impled of iface.implements) {
        members = members.concat(allMembers(db[impled]));
      }
    }
    return members;
  }

  function makeCommand()
  {
    ensureDB();

    if (!Things.has(fuzzerWebIDL.rv) && !isPrimitive(fuzzerWebIDL.rv)) {
      var newb = Things.reserve();
      return newb + " = fuzzerWebIDL.rv;";
    } else {
      fuzzerWebIDL.rv = null;
    }

    if (favoriteTweakers.length && rnd(100)) {
      if (rnd(500) === 0) {
        favoriteTweakers.length = 0;
      } else {
        return Random.index(favoriteTweakers)();
      }
    }

    var i = Random.index(interfaces);
    if (i == "CSS") {
      return "/* nope */"; // XXX do something useful with statics
    }
    if (rnd(10) === 0) {
      return construct(i);
    }
    var instance;
    var reasonable;
    if (rnd(100)) {
      instance = Things.instance(i);
      reasonable = true;
    } else {
      instance = Things.any();
      reasonable = false;
    }
    if (instance == "o[-1]") {
      return construct(i);
    }

    var tweaker = createInstanceTweaker(i, instance, reasonable);
    if (typeof tweaker == "function") {
      if (rnd(30) === 0) {
        favoriteTweakers.push(tweaker);
      }
      return tweaker();
    } else {
      return tweaker;
    }
  }

  return {
    makeCommand: makeCommand,
  };

})();

registerModule("fuzzerWebIDL", 30);

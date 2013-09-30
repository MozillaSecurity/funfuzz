var Logger = (function () {
  var color = { red: "\033[1;31m", green: "\033[1;32m", clear: "\033[0m" };
  var sep = "\n/* ### NEXT TESTCASE ############################## */";

  function console(msg) {
    if (typeof window == 'undefined') {
      print(msg);
    } else if (window.dump) {
      window.dump(msg);
    } else if (window.console && window.console.log) {
      window.console.log(msg);
    } else {
      throw "Unable to run console logger.";
    }
  }

  function dump(msg) { console(msg); }

  function dumpln(msg) { dump(msg + "\n"); }

  function error(msg) { dumpln(color.red + msg + color.clear); }

  function JSError(msg) { error(comment(msg)) }

  function comment(msg) { return "/* " + msg + " */"; }

  function separator() { dumpln(color.green + sep + color.clear); }

  return {
    console: console,
    dump: dump,
    error: error,
    JSError: JSError,
    dumpln: dumpln,
    comment: comment,
    separator: separator
  };
})();


// Todo: Rename to Gadget
var JS = {
  methodHead: function (list, numOptional) {
    if (isNaN(numOptional)) {
      numOptional = 0;
    }
    var arity = list.length - Random.number(numOptional);
    var params = [];
    for (var i = 0; i < arity; i++) {
      params.push(Random.pick([list[i]]));
    }
    return "(" + params.join(", ") + ")";
  },
  methodCall: function (objectName, methodHash) {
    if(!Utils.getKeysFromHash(methodHash).length || !objectName) {
      return "";
    }
    var methodName = Random.key(methodHash);
    var methodArgs = methodHash[methodName];
    return objectName + "." + methodName + JS.methodHead(methodArgs);
  },
  setAttribute: function (objectName, attributeHash) {
    if(!Utils.getKeysFromHash(attributeHash).length || !objectName) {
      return "";
    }
    var attributeName = Random.key(attributeHash);
    var attributeValue = Random.pick(attributeHash[attributeName]);
    var operator = " = ";
    /*
    if (typeof(attributeValue) == "number" && Random.chance(8)) {
      operator = " " + Make.randomAssignmentOperator() + " ";
    }
    if (typeof(attributeValue) == "string") {
     attributeValue = "'" + attributeValue + "'";
    }
    */
    return objectName + "." + attributeName + operator + attributeValue + ";";
  },
  makeConstraint: function (keys, values) {
    var o = {};
    var n = Random.range(0, keys.length);
    while (n--) {
      o[Random.pick(keys)] = Random.pick(values);
    }
    return o;
  },
  safely: function (s) {
    if (window.debug) {
      return "try { " + s + " } catch(e) { Logger.JSError(e); }";
    }
    return "try { " + s + " } catch(e) { }";
  },
  makeLoop: function (s, max) {
    return "for (var i = 0; i < " + (max || Make.rangeNumber()) + "; i++) {" + s + "}";
  },
  makeArray: function (type, arrayLength, cb) {
    if (type == null || type === undefined) {
      type = Random.index(["Uint8", "Float32"]);
    }
    switch (Random.number(8)) {
      case 0:
        var src = "function() { var buffer = new " + type + "Array(" + arrayLength + ");";
        src += JS.makeLoop("buffer[i] = " + cb() + ";", arrayLength);
        src += "return buffer;}()";
        return src;
      case 1:
        return "new " + type + "Array([" + Make.filledArray(cb, arrayLength) + "])";
      default:
        return "new " + type + "Array(" + arrayLength + ")";
    }
  },
  addElementToBody: function (name) {
    return "(document.body || document.documentElement).appendChild" + JS.methodHead([name]) + ";";
  },
  forceGC: function () {
    if (Platform.isMozilla) {}
    if (Platform.isChrome) {
        if (window.GCController)
          return GCController.collect();
    }
    if (Platform.isSafari) {}
    if (Platform.isIE) {}
  }
};


var Utils = {
  objToString: function (obj) {
    try {
      return "" + obj
    } catch (e) {
      return "[" + e + "]"
    }
  },
  getAllProperties: function (obj) {
    var list = [];
    while (obj) {
      list = list.concat(Object.getOwnPropertyNames(obj));
      obj = Object.getPrototypeOf(obj);
    }
    return list;
  },
  getKeysFromHash: function (obj) {
    var list = [];
    for (var p in obj) {
      list.push(p);
    }
    return list;
  },
  quote: function (obj) {
    return JSON.stringify(obj);
  },
  uniqueList: function (list) {
    var tmp = {}, r = [];
    for (var i = 0; i < list.length; i++) {
      tmp[list[i]] = list[i];
    }
    for (var i in tmp) {
      r.push(tmp[i]);
    }
    return r;
  },
  mergeHash: function (obj1, obj2) {
    for (var p in obj2) {
      try {
        if (obj2[p].constructor == Object) {
          obj1[p] = Utils.mergeHash(obj1[p], obj2[p]);
        } else {
          obj1[p] = obj2[p];
        }
      } catch (e) {
        obj1[p] = obj2[p];
      }
    }
    return obj1;
  },
  traceback: function () {
    Logger.error("===[ Traceback ]");
    try {
      throw new Error();
    } catch (e) {
      Logger.dump(e.stack || e.stacktrace || "");
    }
    Logger.error("===");
  }
};


function Block(list, optional) {
  if (optional == true) {
    if (Random.chance(6)) {
      return '';
    }
  }
  function goDeeper(item) {
    if (item == null || item === undefined) {
      return "";
    }
    if (typeof(item) == "function") {
      return item();
    }
    if (typeof(item) == "string") {
      return item;
    }
    if (item instanceof(Array)) {
      var s = "";
      for (var i = 0; i < item.length; i++) {
        s += goDeeper(item[i]);
      }
      return s;
    }
    return item;
  }
  var asString = "";
  for (var i = 0; i < list.length; i++) {
    asString += goDeeper(list[i]);
  }
  return asString;
}

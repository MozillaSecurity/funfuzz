

var fuzzerUndoManager = (function() {

  // DOMTransaction is a "callback interface" -- one that is considered "implemented" by any non-platform object.
  // XXX make a general concept of custom lists
  var transactionIndexes = [];
  function anyTransaction() {
    if (!transactionIndexes.length)
      return null;
    return "o[" + Random.index(transactionIndexes) + "]";
  }

  function addTransactionFunction(t)
  {
    var funName = Random.index(["executeAutomatic", "execute", "redo", "undo"]);
    var lvalue = t + "." + funName;
    return t + "." + funName + " = " + transactionFunction(funName) + ";";
  }

  function transactionFunction(funName)
  {
    switch(rnd(3)) {
      case 0:  return Things.anyFunction();
      case 1:  return "null";
      /// XXX best if it does *several* actions
      default: return "function " + funName + "() { " + fuzzSubCommand("transaction-" + funName) + " }";
    }
  }

  function makeCommand()
  {
    var um = Things.instance("UndoManager");

    // Try to keep the number of undoManagers small, so each one can have a meaningful experience.
    if (um == "o[-1]" || rnd(100) === 0) {
      if (rnd(2)) {
        // Grab an undoManager
        return Things.add(Things.instance(rnd(2) ? "Document" : "Element") + ".undoManager");
      } else {
        // Add an undo scope, and maybe grab the newly created undoManager
        var n = Things.instance("Element");
        return [n + ".undoScope = true;", (rnd(2) ? Things.add(n + ".undoManager") : "")];
      }
    }

    if (rnd(100) === 0) {
      // Destroy something!
      switch(rnd(3)) {
      case 0:
        // Remove an undo scope
        return Things.instance("Element") + ".undoScope = false;";
      case 1:
        // Clear undo stack
        return um + ".clearUndo();";
      default:
        // Clear redo stack
        return um + ".clearRedo();";
      }
    }

    if (rnd(5) === 0) {
      // Create a transaction
      var t = Things.reserve();
      transactionIndexes.push(Things._lastIndex);
      return [t + " = {};", addTransactionFunction(t), addTransactionFunction(t)];
    }

    // Do transaction-level things.
    switch(rnd(4)) {
    case 0:
      // Undo
      return Things.instance("UndoManager") + ".undo();";
    case 1:
      // Redo
      return Things.instance("UndoManager") + ".redo();";
    case 2:
      // Modify a transaction
      return addTransactionFunction(anyTransaction("DOMTransaction"));
    default:
      // Transact. This will either call 'execute' or 'executeAutomatic', and in the latter case,
      // will remember the DOM manipulations in order to be able to undo or redo them.
      return Things.instance("UndoManager") + ".transact(" + anyTransaction("DOMTransaction") + ", " + Random.index(["true", "false"]) + ");";
    }
  }

  return { makeCommand: makeCommand };
})();
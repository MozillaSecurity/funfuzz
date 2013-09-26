

var fuzzerUndoManager = (function() {

  function addTransactionFunction(t)
  {
    var funName = rndElt(["executeAutomatic", "execute", "redo", "undo"]);
    var lvalue = t + "." + funName;
    return t + "." + funName + " = " + transactionFunction(funName) + ";";
  }

  function transactionFunction(funName)
  {
    switch(rnd(3)) {
      case 0:  if (all.functions.length) return pick("functions");
      case 1:  return "null";
      /// XXX best if it does *several* actions
      default: return "function " + funName + "() { " + fuzzSubCommand("transaction-" + funName) + " }";
    }
  }

  function makeCommand()
  {
    // Try to keep the number of undoManagers small, so each one can have a meaningful experience.
    if (all.undoManagers.length == 0 || rnd(100) === 0) {
      if (rnd(2)) {
        // Grab an undoManager
        return addIfNovel("undoManagers", pick(rnd(2) ? "documents" : "nodes") + ".undoManager");
      } else {
        // Add an undo scope, and maybe grab the newly created undoManager
        var n = pick("nodes");
        return [n + ".undoScope = true;", (rnd(2) ? addIfNovel("undoManagers", n + ".undoManager") : "")];
      }
    }

    if (rnd(100) === 0) {
      // Destroy something!
      switch(rnd(3)) {
      case 0:
        // Remove an undo scope
        return pick("nodes") + ".undoScope = false;";
      case 1:
        // Clear undo stack
        return pick("undoManagers") + ".clearUndo();";
      default:
        // Clear redo stack
        return pick("undoManagers") + ".clearRedo();";
      }
    }

    if (all.domTransactions.length == 0 || rnd(5) === 0) {
      // Create a transaction
      var t = nextSlot("domTransactions");
      return [t + " = {};", addTransactionFunction(t), addTransactionFunction(t)];
    }

    // Do transaction-level things.
    switch(rnd(4)) {
    case 0:
      // Undo
      return pick("undoManagers") + ".undo();";
    case 1:
      // Redo
      return pick("undoManagers") + ".redo();";
    case 2:
      // Modify a transaction
      return addTransactionFunction(pick("domTransactions"));
    default:
      // Transact. This will either call 'execute' or 'executeAutomatic', and in the latter case,
      // will remember the DOM manipulations in order to be able to undo or redo them.
      return pick("undoManagers") + ".transact(" + pick("domTransactions") + ", " + rndElt(["true", "false"]) + ");";
    }
  }

  return { makeCommand: makeCommand };
})();
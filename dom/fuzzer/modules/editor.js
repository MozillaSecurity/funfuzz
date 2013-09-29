var fuzzerContentEditable = (function() {

  // https://developer.mozilla.org/en/Rich-Text_Editing_in_Mozilla

  // http://dvcs.w3.org/hg/editing/raw-file/tip/editing.html
  // And its friends:
  //   http://dom.spec.whatwg.org/#ranges
  //   http://dvcs.w3.org/hg/undomanager/raw-file/tip/undomanager.html

  var editorCommands = {
    "backcolor": fuzzValues.colors,
    "bold": null,
    "createlink": fuzzValues.URIs,
    "defaultParagraphSeparator": ["p", "div"], // New in the spec!
    "delete": null,
    "fontname": fuzzValues.fontFaces,
    "fontsize": [
      ["x-small", "small", "medium", "large", "x-large", "xx-large", "xxx-large"],
      function() { return Random.index(["", "+", "-"]) + Random.pick([0, 1, 2, 3, fuzzValues.unsignedNumbers]); }
    ],
    "forecolor": fuzzValues.colors,
    "formatBlock": ["<address>", "<aside>", "<h1>", "<h2>", "<h3>", "<h4>", "<h5>", "<h6>", "<nav>", "<p>", "<pre>", "<blockquote>", function() { return Random.index(fuzzerHTMLAttributes.elemList); }],
    "forwardDelete": null,
    "hilitecolor": fuzzValues.colors,
    "indent": null,
    "inserthorizontalrule": null,
    "inserthtml": fuzzValues.htmlMarkup,
    "insertimage": fuzzValues.URIs,
    "insertLineBreak": null,
    "insertorderedlist": null,
    "insertParagraph": null,
    "insertText": [fuzzValues.texts, fuzzValues.URIs, "", "\n", " ", "a"], // Include URIs because of the "autolink" spec feature
    "insertunorderedlist": null,
    "italic": null,
    "justifycenter": null,
    "justifyfull": null,
    "justifyleft": null,
    "justifynone": null,
    "justifyright": null,
    "outdent": null,
    "redo": null,
    "removeformat": null,
    "selectAll": null,
    "strikethrough": null,
    "styleWithCSS": ["true", "false"],
    "subscript": null,
    "superscript": null,
    "underline": null,
    "undo": null,
    "unlink": null,
    "useCSS": ["true", "false"],

    // Mozilla extensions
    // List from http://mxr.mozilla.org/mozilla-central/source/content/html/document/src/nsHTMLDocument.cpp
    // XXX file a bug to prefix or remove these, as they are spec violations unprefixed
    "contentReadOnly": ["true", "false"],
    "insertBrOnReturn": ["true", "false"],
    "enableInlineTableEditing": ["true", "false"],
    "enableObjectResizing": ["true", "false"],
    "gethtml": null,
    "heading": null,
    "increasefontsize": null,
    "decreasefontsize": null,

    // Other-browser extensions
    "justify": null,
    "unselect": null,

    // Security checked
    "copy": null,
    "paste": null,
    "cut": null,

    // Unknown
    "someUnsupportedCommand": null,
  };

  var allEditorCommands = getKeysFromHash(editorCommands);

  function pickFocusable()
  {
    switch(rnd(10)) {
    case 0:
      return Things.instance("Window");
    case 1:
      return Things.instance("Document");
    default:
      return Things.instance("HTMLElement");
    }
  }

  function contentEditableValue()
  {
    return simpleSource(Random.index(["inherit", "true", "false"]));
  }

  function makeCommand()
  {
    switch(rnd(20)) {
    case 0:
      return pickFocusable() + ".contentEditable = " + contentEditableValue() + ";";
    case 1:
      return Things.instance("Element") + ".setAttribute('contenteditable', " + contentEditableValue() + ");";
    case 2: case 3:
      return pickFocusable() + ".focus();";
    case 4:
      return pickFocusable() + ".select();";
    case 5:
      return Things.instance("Document") + ".queryCommandState(" + simpleSource(Random.index(allEditorCommands)) + ");";
    case 6:
      return Things.instance("Document") + ".queryCommandIndeterm(" + simpleSource(Random.index(allEditorCommands)) + ");";
    case 7:
      return Things.instance("Document") + ".queryCommandSupported(" + simpleSource(Random.index(allEditorCommands)) + ");";
    case 8:
      return Things.instance("Document") + ".queryCommandEnabled(" + simpleSource(Random.index(allEditorCommands)) + ");";
    case 9:
      return Things.instance("Document") + ".queryCommandValue(" + simpleSource(Random.index(allEditorCommands)) + ");";
    case 10:
      return Things.instance("HTMLElement") + ".spellcheck = " + Random.index(["true", "false"]) + ";";
    case 11:
      return "document.designMode = 'on';";
    case 12:
      return "document.designMode = 'off';";
    default:
      var editorCommand = Random.index(allEditorCommands);
      var showUI = Random.index(["true", "false"]);
      var value = Random.pick(editorCommands[rnd(10) ? editorCommand : Random.index(allEditorCommands)]);
      return Things.instance("Document") + ".execCommand(" + simpleSource(editorCommand) + ", " + showUI + ", " + simpleSource(value) + ");";
    }
  }

  return { makeCommand: makeCommand };
})();

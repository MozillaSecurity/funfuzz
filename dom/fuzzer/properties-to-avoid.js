// Avoid using these IDL properties/methods "accidentally", as they might
// toss up modal dialogs or navigate away from the page.

var annoyingProperties = [
  {
    iface: "Window",
    props: {
      "print": 1,
      "alert": 1,
      "prompt": 1,
      "confirm": 1,
      "find": 1,
      "showModalDialog": 1,
      "openDialog": 1,
      "history": 1,
      "location": 1,
    },
  },
  {
    iface: "External",
    props: {
      "addSearchEngine": 1,
      "AddSearchProvider": 1, // see bug 839736
    },
  },
  {
    iface: "Document",
    props: {
      "location": 1,
    },
  },
  {
    iface: "HTMLDocument",
    props: {
      "open": 1,
      "write": 1,
      "writeln": 1,
    },
  },
  {
    iface: "XPathEvaluator",
    props: {
      "evaluate": 1, // frequent crashes (bug 949990)
    }
  },
  {
    iface: "CanvasRenderingContext2D",
    props: {
      "arc": 1, // hangy
    }
  },
  {
    iface: "Location",
    props: {
      "assign": 1,
      "reload": 1,
      "replace": 1,
    },
  },
  {
    iface: "History",
    props: {
      "back": 1,
      "forward": 1,
      "go": 1,
    },
  },
  {
    iface: "HTMLAnchorElement",
    props: {
      "click": 1,
    },
  },
  {
    iface: "HTMLFormElement",
    props: {
      "submit": 1,
    },
  },
];

function propertyIsAnnoying(obj, prop)
{
  for (var entry of annoyingProperties) {
    if ((entry.iface in window) && (obj instanceof window[entry.iface]) && (prop in entry.props)) {
      return true;
    }
  }
  return false;
}

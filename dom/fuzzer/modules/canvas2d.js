/*
 * Canvas2D References
 *
 * Specification: http://www.w3.org/html/wg/drafts/2dcontext/html5_canvas/
 * Firefox WebIDL: dom/webidl/CanvasRenderingContext2D.webidl
 * Mochitests: content/canvas/test/
 *
**/
var fuzzerCanvas2D = (function() {

  function contextAttributes() {
    // Generate a 'dictionary ContextAttributes2D'
    return "{ willReadFrequently: " + Make.bool() + ", alpha: " + Make.bool() + " }";
  }

  function makeCommand()
  {
    if (!Things.hasInstance("HTMLCanvasElement") || rnd(20) == 0) {
      var newCanvas = Things.reserve();
      return [
        newCanvas + " = document.createElementNS('http://www.w3.org/1999/xhtml', 'canvas');",
        JS.addElementToBody(newCanvas)
      ];
    }

    if (!Things.hasInstance("CanvasRenderingContext2D") || rnd(20) == 0) {
      return Things.add(Things.instance("HTMLCanvasElement") + ".getContext('2d', " + contextAttributes() + ")");
    }

    if (!Things.hasInstance("HTMLImageElement")) {
      var newImage = Things.reserve();
      return [
        newImage + " = document.createElementNS('http://www.w3.org/1999/xhtml', 'img');",
        newImage + ".src = " + Make.image() + ";"
      ];
    }

    if (!Things.hasInstance("HTMLVideoElement") && Random.chance(800)) {
      var newVideo = Things.reserve();
      return [
        newVideo + " = document.createElementNS('http://www.w3.org/1999/xhtml', 'video');",
        newVideo + ".src = " + Make.video() + ";"
      ];
    }

    if (Random.chance(8)) {
      return JS.setAttribute(Things.instance("CanvasRenderingContext2D"), CanvasRenderingContext2DAttributes);
    }

    if (Random.chance(4)) {
      return _DrawImage();
    }

    if (!Things.hasInstance("ImageData") || Random.chance(32)) {
      return _ImageData();
    }

    if (Things.hasInstance("ImageData") && Random.chance(16)) {
      return _putImageData();
    }

    if (!Things.hasInstance("CanvasGradient") || Random.chance(32)) {
      return _CanvasGradient();
    }

    if (!Things.hasInstance("CanvasPattern") && Random.chance(32)) {
      return _CanvasPattern();
    }

    if (Things.hasInstance("HTMLCanvasElement") && Random.chance(16)) {
      return JS.setAttribute(Things.instance("HTMLCanvasElement"), CanvasRenderingContext2DElementAttributes);
    }

    if (Things.hasInstance("CanvasGradient") && Random.chance(16)) {
      return JS.methodCall(Things.instance("CanvasGradient"), CanvasGradientMethods) + ";";
    }

    if (Random.chance(1000)) {
      return convertFromCanvas();
    }

    return JS.methodCall(Things.instance("CanvasRenderingContext2D"), CanvasRenderingContext2DMethods) + ";";
  }

  function convertFromCanvas()
  {
    var choice = Random.range(0, 4);
    if (choice == 0) {
      return Things.add(Things.instance("HTMLCanvasElement") + ".toDataURL" + JS.methodHead([Utils.quote(Make.imageMimeType())]));
    }
    if (Platform.isMozilla && choice == 1) {
      var args = ["function() {}", Utils.quote(Make.imageMimeType()), Make.number];
      return Things.add(Things.instance("HTMLCanvasElement") + ".toBlob" + JS.methodHead(args));
    }
    if (Platform.isMozilla && choice == 2) {
      var args = [Utils.quote(Make.image())];
      return Things.add(Things.instance("HTMLCanvasElement") + ".mozGetAsFile" + JS.methodHead(args));
    }
    return [];
  }

  /*
  ** Constructors.
  */
  function _CanvasGradient() {
    // Firefox defines an overloaded function with 4 parameters but throws an error?
    return Things.reserve() + " = " + Things.instance("CanvasRenderingContext2D") + ".createRadialGradient" + JS.methodHead(
      [Make.number, Make.number, Make.number, Make.number, Make.number, Make.number]) + ";";
  }

  function _CanvasPattern() {
    var params = [Things.instance("HTMLCanvasElement"), ["'repeat'", "'repeat-x'", "'repeat-y'", "'no-repeat'"]];
    return Things.reserve() + " = " + Things.instance("CanvasRenderingContext2D") + ".createPattern" + JS.methodHead(params) + ";";
  }

  function _ImageData() {
    var params;
    var choice = Random.number(6);
    if (choice == 0) {
      params = [Make.number, Make.number, Make.number, Make.number];
      return Things.reserve()  + " = " + Things.instance("CanvasRenderingContext2D") + ".getImageData" + JS.methodHead(params) + ";";
    }
    if (choice == 1 && Things.hasInstance("ImageData")) {
      params = [Things.instance("ImageData")];
      return Things.reserve() + " = " + Things.instance("CanvasRenderingContext2D") + ".createImageData" + JS.methodHead(params) + ";";
    }
    params = [Make.number, Make.number];
    return Things.reserve() + " = " + Things.instance("CanvasRenderingContext2D") + ".createImageData" + JS.methodHead(params) + ";";
  }

  function _DrawImage() {
    var params,
        elementName = Things.instance(Random.pick(Things.filterHasInstance(["HTMLCanvasElement", "HTMLImageElement", "HTMLVideoElement"])));
    if (Platform.isChrome && Random.chance(4)) {
      params = [elementName];
      for (var i = 0; i < 8; ++i) {
        params.push(Make.number());
      }
      return Things.instance("CanvasRenderingContext2D") + ".drawImageFromRect" + JS.methodHead(params) + ";";
    }
    params = Random.choose([
      [1, [elementName, Make.number(), Make.number()]],
      [1, [elementName, Make.number(), Make.number(), Make.number(), Make.number()]],
      [1, [elementName, Make.number(), Make.number(), Make.number(), Make.number(), Make.number(), Make.number(), Make.number(), Make.number()]]
      ], true);
    return Things.instance("CanvasRenderingContext2D") + ".drawImage" + JS.methodHead(params) + ";";
  }

  function _putImageData() {
    var params;
    if (Platform.isChrome && Random.chance(4)) {
      params = Random.choose([
        [1, [Things.instance("ImageData"), Make.number(), Make.number()]],
        [1, [Things.instance("ImageData"), Make.number(), Make.number(), Make.number(), Make.number(), Make.number(), Make.number()]]
      ], true);
      return Things.instance("CanvasRenderingContext2D") + ".webkitPutImageDataHD" + JS.methodHead(params) + ";";
    }
    params = Random.choose([
      [1, [Things.instance("ImageData"), Make.number(), Make.number()]],
      [1, [Things.instance("ImageData"), Make.number(), Make.number(), Make.number(), Make.number(), Make.number(), Make.number()]]
    ], true);
    return Things.instance("CanvasRenderingContext2D") + ".putImageData" + JS.methodHead(params) + ";";
  }

  /*
  ** Methods and attributes.
  */
  function canvasDim() { return Math.floor(Math.pow(2, Random.float() * 17)) - 1; }
  var CanvasRenderingContext2DElementAttributes = {
    "width": [canvasDim],
    "height": [canvasDim]
  };
  if (Platform.isMozilla) {
    Utils.mergeHash(CanvasRenderingContext2DElementAttributes, {
      "mozOpaque": [Make.bool]
    });
  }

  var CanvasWindingRule = ["'nonzero'", "'evenodd'"];

  var CanvasRenderingContext2DAttributes = {
    "globalAlpha": [Make.number],
    "globalCompositeOperation": ["'source-atop'", "'source-in'", "'source-out'", "'source-over'", "'destination-atop'",
      "'destination-in'", "'destination-out'", "'destination-over'", "'lighter'", "'copy'", "'exclusion'"],
    "strokeStyle": [Make.color],
    "fillStyle": [Make.color],
    "shadowOffsetX": [Make.number],
    "shadowOffsetY": [Make.number],
    "shadowBlur": [Make.number],
    "shadowColor": [Make.color],
    "lineWidth": [1, Make.number],
    "lineCap": ["'butt'", "'round'", "'square'"],
    "lineJoin": ["'round'", "'bevel'", "'miter'"],
    "miterLimit": [10, Make.number],
    "font": [Make.font],
    "textAlign": ["'start'", "'end'", "'left'", "'right'", "'center'"],
    "textBaseline": ["'top'", "'hanging'", "'middle'", "'alphabetic'", "'ideographic'", "'bottom'"]
  };
  if (Platform.isMozilla) {
    Utils.mergeHash(CanvasRenderingContext2DAttributes, {
      "mozImageSmoothingEnabled": [Make.bool],
      "mozDashOffset": [Make.number],
      /*"mozDash": [function() { // Bug: 899517
        return Utils.quote(Make.filledArray(function() { return Random.pick([0,1]); }, Random.range(0, 32)))}
      ],*/
      "mozFillRule": [CanvasWindingRule],
      "mozCurrentTransform": [function() {
        return Utils.quote(Make.filledArray(function() { return Random.pick([Make.number]); }, 6)) }
      ],
      "mozCurrentTransformInverse": [function() {
        return Utils.quote(Make.filledArray(function() { return Random.pick([Make.number]); }, 6)) }
      ]
    });
  }
  if (Platform.isChrome) {
    Utils.mergeHash(CanvasRenderingContext2DAttributes, {
      "webkitImageSmoothingEnabled": [Make.bool],
      "lineDashOffset": [Make.number]
    });
  }

  var CanvasRenderingContext2DMethods = {
    "save": [],
    "restore": [],
    "scale": [Make.number, Make.number],
    "rotate": [Make.number],
    "translate": [Make.number, Make.number],
    "transform": [Make.number, Make.number, Make.number, Make.number, Make.number, Make.number],
    "setTransform": [Make.number, Make.number, Make.number, Make.number, Make.number, Make.number],
    "clearRect": [Make.number, Make.number, Make.number, Make.number],
    "fillRect": [Make.number, Make.number, Make.number, Make.number],
    //"strokeRect": [Make.number, Make.number, Make.number, Make.number], // Bug: 899517
    "beginPath": [],
    "fill": [CanvasWindingRule],
    //"stroke": [], // Bug: 899517
    "clip": [CanvasWindingRule],
    "isPointInPath": [Make.number, Make.number, CanvasWindingRule],
    "isPointInStroke": [
      function() { return Random.choose([
        [20, Make.tinyNumber],
        [ 1, Make.number]
       ])},
      function () { return Random.choose([
        [20, Make.tinyNumber],
        [ 1, Make.number]
      ])}
    ],
    "fillText": [function() {
        return Random.choose([
          [1, [Make.quotedString(), Make.number(), Make.number()]],
          [1, [Make.quotedString(), Make.number(), Make.number(), Make.number()]]
        ], true);
      },
    ],
    "strokeText":  [function() {
        return Random.choose([
          [1, [Make.quotedString(), Make.number(), Make.number()]],
          [1, [Make.quotedString(), Make.number(), Make.number(), Make.number()]]
        ], true);
      },
    ],
    "measureText": [Make.quotedString],
    "closePath": [],
    "moveTo": [Make.number, Make.number],
    "lineTo": [Make.number, Make.number],
    "quadraticCurveTo": [Make.number, Make.number, Make.number, Make.number],
    "bezierCurveTo": [Make.number, Make.number, Make.number, Make.number, Make.number, Make.number],
    "rect": [Make.number, Make.number, Make.number, Make.number],
    "arcTo": [Make.number, Make.number, Make.number, Make.number, Make.number],
    "arc": [
      function() { return Random.choose([
        [20, Make.tinyNumber],
        [ 1, Make.number]
      ])},
      function() { return Random.choose([
        [20, Make.tinyNumber],
        [ 1, Make.number]
      ])},
      function () { return Random.choose([
        [20, Make.tinyNumber],
        [ 1, Make.number]
      ])},
      function () { return Random.choose([
        [20, Make.tinyNumber],
        [ 1, Make.number]
      ])},
      function () { return Random.choose([
        [20, Make.tinyNumber],
        [ 1, Make.number]
       ])},
       Make.bool
    ]
  };
  if (Platform.isCrome) {
    Utils.mergeHash(CanvasRenderingContext2DMethods, {
      "createLinearGradient": [function() {
          return Random.choose([
            [1, [Make.number(), Make.number(), Make.number(), Make.number()]],
            [1, [Make.number(), Make.number(), Make.number(), Make.number(), Make.number(), Make.number()]]
          ], true);
        }
      ],
      "setAlpha": [Make.number],
      "setCompositeOperation": ["'source-atop'", "'source-in'", "'source-out'", "'source-over'", "'destination-atop'",
        "'destination-in'", "'destination-out'", "'destination-over'", "'lighter'", "'copy'", "'exclusion'"],
      "getLineDash": [],
      "setLineDash": [function () {
        return Utils.quote(Make.filledArray(function () { return Random.pick([0, 1]); }, Random.range(0, 32)))}
      ],
      "setLineWidth": [Make.number],
      "setLineCap": ["'butt'", "'round'", "'square'"],
      "setLineJoin": ["'round'", "'bevel'", "'miter'"],
      "setMiterLine": [Make.number],
      "setStrokeColor": [function() {
          return Random.choose([
            [1, [Make.color(), Make.number()]],
            [1, [Make.number(), Make.number()]],
            [1, [Make.number(), Make.number(), Make.number(), Make.number()]],
            [1, [Make.number(), Make.number(), Make.number(), Make.number(), Make.number()]]
          ], true);
        }
      ],
      "setFillColor": [function () {
          return Random.choose([
            [1, [Make.color(), Make.number()]],
            [1, [Make.number(), Make.number()]],
            [1, [Make.number(), Make.number(), Make.number(), Make.number()]],
            [1, [Make.number(), Make.number(), Make.number(), Make.number(), Make.number()]]
          ], true);
        }
      ],
      "strokeRect": [Make.number, Make.number, Make.number, Make.number],
      "clearShadow": [],
      "setShadow": [function() {
          return Random.choose([
            [1, [Make.number(), Make.number(), Make.number(), Make.color(), Make.number()]],
            [1, [Make.number(), Make.number(), Make.number(), Make.number(), Make.number()]],
            [1, [Make.number(), Make.number(), Make.number(), Make.number(), Make.number(), Make.number(), Make.number()]],
            [1, [Make.number(), Make.number(), Make.number(), Make.number(), Make.number(), Make.number(), Make.number(), Make.number()]]
          ], true);
        }
      ],
      "webkitGetImageDataHD": [Make.number, Make.number, Make.number, Make.number],
      "getContextAttributes": []
    });
  }

  var CanvasGradientMethods = {
    "addColorStop": [[0.0, 1.0, Make.float], Make.color]
  };

  return {
    makeCommand: makeCommand,
  };
})();

registerModule("fuzzerCanvas2D", 20);

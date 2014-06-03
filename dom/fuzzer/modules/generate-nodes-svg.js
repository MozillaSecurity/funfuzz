var fuzzerSVGAttributes = (function() {

  // http://www.w3.org/TR/SVG/struct.html#Head gives a list of things that reference and can be referenced :)
  var gradientIDs = function() { return "grad" + rnd(3); };
  var patternIDs = function() { return "pat" + rnd(3); };
  var pserverIDs = [gradientIDs, patternIDs];
  var symbolIDs = function() { return "symb" + rnd(3); };
  var textIDs = function() { return "text" + rnd(3); };
  var pathIDs = function() { return "path" + rnd(3); };
  var markerIDs = ["marker6", function() { return "marker" + rnd(3); }];
  var filterIDs = function() { return "filter" + rnd(3); };
  var filterLocalNames = ["a", "b", "c", "d", "e", "SourceGraphic", "SourceAlpha", "BackgroundImage", "BackgroundAlpha", "FillPaint", "StrokePaint"];
  var clipPathIDs = function() { return "clippath" + rnd(3); };
  var maskIDs = function() { return "mask" + rnd(3); };

  function idAsHref(x) { return function() { return "#" + Random.pick(x); }; }
  function idAsCssRef(x) { return function() { return "url(#" + Random.pick(x) + ")"; }; }

  var anythingIDs = function() { return Random.pick([symbolIDs, textIDs, pathIDs, markerIDs, filterIDs, clipPathIDs, maskIDs, filterLocalNames, fuzzValues.names]); };


  var opacities = ["0", ".2", ".3", ".5", ".8", "1"];
  var angles = ["0deg", "30deg", "45deg", "60deg", "1rad", "90deg", "180deg", "270deg", "360deg"];
  var transforms = [["translate(20,2.5)", "rotate(10)", "skewY(30)", "skewX(30)", "scale(3)", "scale(.2)"], ""];
  var paints = ["none", "inherit", "currentColor", fuzzValues.colors, idAsCssRef(pserverIDs)];

  var svgLengths = fuzzValues.numbersWithUnits; // unitless numbers are special in SVG, but numbersWithUnits does that plenty.
  var svgSmallLengths = [1, 2, 3, 4, 5, 6, 7, 8, 9, svgLengths];

  var commonAttributes = ["id", "name", "color", "opacity", "fill", "fill-rule", "fill-opacity", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-miterlimit", "stroke-dasharray", "stroke-dashoffset", "stroke-opacity", "transform", "display", "visibility"];


  var attributes = {
    "randomness": fuzzTotallyRandomValue,

    // http://www.w3.org/TR/SVG11/types.html

    "id": fuzzValues.names,
    "name": fuzzValues.names,
    "color": fuzzValues.colors,
    "opacity": opacities,

    "fill": paints,
    "fill-rule": ["nonzero", "evenodd"],
    "fill-opacity": opacities,

    "stroke": paints,
    "stroke-width": svgSmallLengths,

    "stroke-linecap": ["butt", "round", "square"],
    "stroke-linejoin": ["miter", "round", "bevel"],
    "stroke-miterlimit": [4, 1, 9, fuzzValues.numbers],

    "stroke-dasharray": ["none", "5,3,2", "3,3"],
    "stroke-dashoffset": [0, 1, 4, fuzzValues.numbers],
    "stroke-opacity": opacities,

    "display": ["none", "inline", "block", "inline-block"], // wtf
    "visibility": ["visible", "hidden", "collapse"], // wtf

    "x": svgLengths,
    "y": svgLengths,
    "width": svgLengths,
    "height": svgLengths,
    "rx": svgLengths,
    "ry": svgLengths,
    "cx": svgLengths,
    "cy": svgLengths,
    "x1": svgLengths,
    "x2": svgLengths,
    "y1": svgLengths,
    "y2": svgLengths,
    "viewBox": "0 0 30 40",
    "preserveAspectRatio": ["xMaxYMax meet", "xMidYMid slice", "xMidYMid meet"],
    "zoomAndPan": ["disable", "magnify"],
    "xlink:href": [idAsHref(anythingIDs), fuzzValues.URIs],
    "transform": transforms,
    "requiredFeatures": ["", "foo", "http://www.w3.org/TR/SVG11/feature#Gradient"],
    "requiredExtensions": ["", "", "", "http://example.com/SVGExtensions/EmbeddedXHTML", "foopy"],

    // http://www.w3.org/TR/SVG11/masking.html#OverflowAndClipProperties
    "overflow": ["visible", "hidden", "scroll", "auto", "inherit"],
    "clip": ["auto", "rect(5px, 10px, 10px, 5px)", "rect(5px, -5px, 10px, 5px)"],

    "d": [
      "M100,200 C100,100 250,100 250,200 S400,300 400,200",
      "M600,350 l 50,-25 a25,25 -30 0,1 50,-25 l 50,-25 a25,50 -30 0,1 50,-25 l 50,-25 a25,75 -30 0,1 50,-25 l 50,-25 a25,100 -30 0,1 50,-25 l 50,-25"
    ],
    "points": [
      "50,375 150,375 150,325 250,325 250,375 350,375 350,250 450,250 450,375 550,375 550,175 650,175 650,375 750,375 750,100 850,100 850,375 950,375 950,25 1050,25 1050,375 1150,375", // rectangles
      "350,75  379,161 469,161 397,215 423,301 350,250 277,301 303,215 231,161 321,161" // star
    ],
    "dx": svgLengths,
    "dy": svgLengths,
    "rotate": ["0", "0 10 20 30 40 50 60 70 80"],
    "lengthAdjust": ["spacing", "spacing", "spacing", "spacingAndGlyphs"],
    "writing-mode": ["lr-tb", "lr", "rl-tb", "rl", "tb-rl", "tb"],
    "direction": ["ltr", "rtl"],
    "unicode-bidi": ["normal", "embed", "bidi-override", "inherit"],
    "text-anchor": ["start", "middle", "end"],
    "dominant-baseline": ["auto", ["use-script", "no-change", "reset-size", "ideographic", "alphabetic", "hanging", "mathematical", "central", "middle", "text-after-edge", "text-before-edge", "inherit"]],
    "alignment-baseline": ["auto", ["baseline", "before-edge", "text-before-edge", "middle", "central", "after-edge", "text-after-edge", "ideographic", "alphabetic", "hanging", "mathematical", "inherit"]],
    "baseline-shift": ["baseline", ["sub", "super", fuzzValues.percents, svgLengths, "inherit"]],
    "kerning": ["auto", svgSmallLengths],
    "letter-spacing": ["auto", svgSmallLengths],
    "word-spacing": ["auto", svgSmallLengths],
    "text-decoration": ["none", ["underline", "overline", "line-through", "blink"]],

    "marker-start": ["", idAsCssRef(markerIDs)],
    "marker-end": ["", idAsCssRef(markerIDs)],
    "marker-mid": ["", idAsCssRef(markerIDs)],
    "marker": ["", idAsCssRef(markerIDs)],

    // marker
    "markerUnits": ["strokeWidth", "userSpaceOnUse"],
    "markerWidth": svgLengths,
    "markerHeight": svgLengths,
    "orient": ["auto", angles],

    // gradient
    "gradientUnits": ["userSpaceOnUse", "objectBoundingBox"],
    "gradientTransform": transforms,
    "spreadMethod": ["pad", "reflect", "repeat", "default"],

    // radialGradient
    "r": svgLengths,
    "fx": ["", svgLengths],
    "fy": ["", svgLengths],

    // stop
    "offset": [fuzzValues.numbers, svgLengths], // :( and ??
    "stop-color": fuzzValues.colors,
    "stop-opacity": opacities,

    // pattern
    "patternUnits": ["userSpaceOnUse", "objectBoundingBox"],
    "patternContentUnits": ["userSpaceOnUse", "objectBoundingBox"],
    "patternTransform": transforms,

    // filter
    "filterUnits": ["userSpaceOnUse", "objectBoundingBox"],
    "filterRes": [fuzzValues.twoNumbers, fuzzValues.numbers],

    "in": filterLocalNames,
    "in2": filterLocalNames,
    "result": filterLocalNames,

    "scale": fuzzValues.numbers,
    "xChannelSelector": ["R", "G", "B", "A"],
    "yChannelSelector": ["R", "G", "B", "A"],

    "mode": ["normal", "multiply", "screen", "darken", "lighten"],  // feBlend

    "type": ["matrix", "saturate", "hueRotate", "luminanceToAlpha", // feColorMatrix
             "identity", "table", "discrete", "linear", "gamma"],   // feComponentTransfer, feFunc*

    "values":
      ["1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 1 0", // matrix: identity
       "1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0", // matrix: only keep red
       ".3", "0", "1", "1.3", "90", "180", "720", "-600", fuzzValues.numbers],

    "slope": fuzzValues.numbers,
    "intercept": fuzzValues.numbers,
    "amplitude": fuzzValues.numbers,
    "exponent": fuzzValues.numbers,
    "tableValues": [".5", "9", "0 1 2", "", "0 .1 .2 .3 .4 .5 .6 .7 .8 .9 1", ".3 .7 .5", "3 7 5", "0 0 1 1", "1 1 0 0", "0 1 1 0", fuzzValues.numbers],
    "operator": [
       "over", "in", "out", "atop", "xor", "arithmetic", "k1", "k2", "k3", "k4", // feComposite
       "dilate", "erode" // feMorphology
     ],
    "radius": [fuzzValues.twoNumbers, fuzzValues.numbers],
    "k1": fuzzValues.numbers,
    "k2": fuzzValues.numbers,
    "k3": fuzzValues.numbers,
    "k4": fuzzValues.numbers,

    "stdDeviation": ["", fuzzValues.twoNumbers, fuzzValues.numbers],

    "clip-path": ["none", idAsCssRef(clipPathIDs)],
    "clip-rule": ["nonzero", "evenodd"],

    "mask": [idAsCssRef(maskIDs)],
    "maskUnits": ["userSpaceOnUse", "objectBoundingBox"],
    "maskContentUnits": ["userSpaceOnUse", "objectBoundingBox"],

    // feConvolveMatrix
    "order": [fuzzValues.twoNumbers],
    "kernelMatrix":
      ["0.1111 0.1111 0.1111 0.1111 0.1111 0.1111 0.1111 0.1111 0.1111",
       "-1 -1 -1 -1 8 -1 -1 -1 -1",
       "-1 -1 -1 -1 9 -1 -1 -1 -1",
       "-2 0 0 0 1 0 0 0 2",
       "0.3333 0.3333 0.3333",
       "0.3333 0.3333 0.3333"],
    "egdeMode": ["none", "duplicate", "wrap"],
    "divisor": ["1.3", "0.5", "0", "-1", "1", fuzzValues.numbers],
    "bias": ["1.3", "0.5", "0", "-1", "1", fuzzValues.numbers],
    "targetX": ["-1", "3", fuzzValues.numbers],
    "targetY": ["-1", "3", fuzzValues.numbers],
    "kernelUnitLength": [fuzzValues.twoNumbers, fuzzValues.numbers],
    "preserveAlpha": fuzzValues.booleans


  };


  var filterPrimitiveAttributes = ["x", "y", "width", "height", "result", "in", "in2", "mode", "type", "values", "tableValues", "slope", "intercept", "amplitude", "exponent", "offset", "operator", "stdDeviation"];


  // "foo" means look it up in the attributes array to find a value.
  // ["foo", bar] means use bar to find a value.  (used on very overloaded attributes, such as "id")

  var elements =
  {
    // http://www.w3.org/TR/SVG11/shapes.html
    "rect": ["x", "y", "width", "height", "rx", "ry", "clip-path", "clip-rule", "mask"],
    "circle": ["cx", "cy", "r"],
    "ellipse": ["cx", "cy", "rx", "ry"],

    "g": [],
    "svg": ["x", "y", "width", "height", "viewBox", "preserveAspectRatio", "zoomAndPan", "overflow", "clip"], // "Another use for 'svg' elements within the middle of SVG content is to establish a new viewport." -- http://www.w3.org/TR/SVG/struct.html
    "title": [],
    "desc": [],

    // These need attributes!
    "script": [],
    "animate": [],
    "set": [],

    "symbol": ["viewbox", ["id", symbolIDs], "overflow", "clip"],
    "use": ["x", "y", "width", "height", ["xlink:href", [idAsHref(anythingIDs), idAsHref(symbolIDs)]], "transform", "overflow", "clip"],
    "image": ["x", "y", "width", "height", ["xlink:href", fuzzValues.URIs]],
    "switch": [],
    "line": ["x1", "x2", "y1", "y2", "marker-start", "marker-mid", "marker-end", "marker"],
    "path": ["d", ["id", pathIDs], "marker-start", "marker-mid", "marker-end", "marker"],
    "polyline": ["points", "marker-start", "marker-mid", "marker-end", "marker"],
    "polygon": ["points", "marker-start", "marker-mid", "marker-end", "marker"],

    // all text stuff WAS commented out, too many assertions
    "text": ["x", "y", "dx", "dy", "rotate", /* "textLength", */ "lengthAdjust", ["id", textIDs], "writing-mode"],
    "tspan": ["x", "y", "dx", "dy", "rotate", /* "textLength", */ "lengthAdjust", ["id", textIDs]],
    "tref": ["x", "y", "dx", "dy", "rotate", ["xlink:href", idAsCssRef(textIDs)]],
    "textPath": [["xlink:href", idAsCssRef(pathIDs)]],

    "marker": ["markerUnits", "markerWidth", "markerHeight", "orient", ["id", markerIDs], "overflow", "clip"], // also refX and refY, skipping

    "linearGradient": ["gradientUnits", "gradientTransform", "x1", "y1", "x2", "y2", "spreadMethod", ["id", gradientIDs], ["xlink:href", idAsCssRef(gradientIDs)]],
    "radialGradient": ["gradientUnits", "gradientTransform", "cx", "cy", "r", "fx", "fy", "spreadMethod", ["id", gradientIDs], ["xlink:href", idAsCssRef(gradientIDs)]],
    "stop": ["offset", "stop-color", "stop-opacity"],

    "pattern": ["patternUnits", "patternContentUnits", "patternTransform", "x", "y", "width", "height", ["id", patternIDs], ["xlink:href", idAsCssRef(patternIDs)], "overflow", "clip"],

    "foreignObject": ["x", "y", "width", "height", "requiredExtensions", "overflow", "clip"],

    // filters?

    // http://lxr.mozilla.org/mozilla/source/content/svg/content/src/nsSVGElementList.h#73 shows which gecko supports, but it LIES!
    // perhaps http://lxr.mozilla.org/mozilla/source/layout/base/nsCSSFrameConstructor.cpp#7222 would tell me the truth?

    "filter": ["x", "y", "width", "height", "filterRes", "filterUnits", "primitiveUnits", ["id", filterIDs], ["xlink:href", idAsCssRef(filterIDs)]],
    "feBlend": filterPrimitiveAttributes,
    "feColorMatrix": filterPrimitiveAttributes,
    "feComponentTransfer": filterPrimitiveAttributes,
    "feDisplacementMap": filterPrimitiveAttributes.concat(["scale", "xChannelSelector", "yChannelSelector"]),
    "feImage": filterPrimitiveAttributes.concat(["preserveAspectRatio", "xlink:href"]),
    "feFuncR": filterPrimitiveAttributes,
    "feFuncG": filterPrimitiveAttributes,
    "feFuncB": filterPrimitiveAttributes,
    "feFuncA": filterPrimitiveAttributes,
    "feComposite": filterPrimitiveAttributes.concat(["operator", "k1", "k2", "k3", "k4", "in2"]),
    "feGaussianBlur": filterPrimitiveAttributes,
    "feMorphology": filterPrimitiveAttributes.concat(["operator", "radius"]),
    "feConvolveMatrix": filterPrimitiveAttributes.concat(
      ["order", "kernelMatrix", "egdeMode", "divisor", "bias", "targetX", "targetY", "kernelUnitLength", "preserveAlpha"]),

    "clipPath": ["clipPathUnits", ["id", clipPathIDs]],

    "mask": ["maskUnits", "maskContentUnits", "x", "y", "width", "height", ["id", maskIDs]]


    // clipPath?
    //  http://www.w3.org/TR/SVG11/masking.html#MaskElement
    // mask?


    // animation?
  };

  // XXX http://www.w3.org/TR/SVG/filters.html#AccessingBackgroundImage (needs CSS munging)

  return {
    makeCommand: eaCommandMaker("http://www.w3.org/2000/svg", elements, attributes, commonAttributes),

    // exported for fuzzerRandomClasses
    gradientRefs: idAsCssRef(gradientIDs),
    filterRefs: idAsCssRef(filterIDs),
    clipPathRefs: idAsCssRef(clipPathIDs),
    maskRefs: idAsCssRef(maskIDs),

    elemHash: elements,
    attrHash: attributes,
    elemList: getKeysFromHash(elements),
    attrList: getKeysFromHash(attributes)
  };
})();

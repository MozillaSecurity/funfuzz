


var fuzzerCanvas = (function() {

  var myCanvas = null;
  var myContext = null;

  // Concentrate on small numbers for now, because larger numbers often hang.
  var numbers = function() { if (rnd(100)) return rnd(1000)/(rnd(10)+1); return randomThing(fuzzValues.jsNumbers); };

  var texts = function() { return simpleSource(randomThing(fuzzValues.texts)); };
  var colors = function() { return simpleSource(randomThing(fuzzValues.colors)); };
  var numbersZeroOne = fuzzValues.numbersZeroOne;

  function inputImages() { return pick("nodes"); }

  function makeCommand()
  {
    function totallyRandomThing()
    {
      return randomThing([numbers, texts, CreateStyle, colors, inputImages, [0,"0",.5,1,-.5,-1,rnd(1000), rndr()]]);
    }

    if (!myCanvas || rnd(100) === 0) {
      myCanvas = nextSlot("nodes");

      // On my MacBook pro (early 2011), canvas drawing starts to fail
      // around 20000 x 20000 (but the failure is not reported to JS).

      var w = Math.floor(Math.pow(2, rnd.rndReal() * 15)) - 1;
      var h = Math.floor(Math.pow(2, rnd.rndReal() * 15)) - 1;

      return [
        myCanvas + " = document.createElementNS('http://www.w3.org/1999/xhtml', 'canvas');",
        myCanvas + ".setAttribute('width', " + w + ");",
        myCanvas + ".setAttribute('height', " + h + ");",
        "(document.body || document.documentElement).appendChild(" + myCanvas + ");"
      ];
    }

    if (!myContext || rnd(100) === 0) {
      myContext = nextSlot("nodes");
      return myContext + " = " + myCanvas + ".getContext('2d');";
    }

    if (rnd(800) === 0) {
      myContext = nextSlot("nodes");
      return myContext + " = " + myCanvas + ".getContext('experimental-webgl');";
    }

    switch (rnd(6)) {
    case 0:
    case 1:
    case 2:
      // Change a canvas context attribute
      var attr = rndElt(allattribs);
      var value = randomThing(rnd(5)==1 ? totallyRandomThing : attributes[attr]);
      return myContext + "." + attr + " = " + value + ";";

    case 3:
    case 4:
    case 5:
      // Call a canvas context method
      var methd = rndElt(allmethods);
      var arglist = methods[methd];

      var command = myContext + "." + methd + "(";
      var argvalue;

      // Test optional arguments by randomly truncating the argument list.
      var numArgs = rnd(10) ? arglist.length : rnd(arglist.length + 1);

      for (var i=0;i<numArgs;i++){
        argvalue = randomThing(rnd(5)==1 ? totallyRandomThing : arglist[i]);
        command += argvalue;
        if (i+1<numArgs)
          command += ", ";
      }
      command += ");";
      return command;
    }

    return command;

  }


    function rndr(){
      //returns a random real number up to the 4th decimal
      // (could be replaced with a call to numbersZeroOne)
      return rnd(1000)/1000;
    }


    function CreateStyle(){
      //creates a random style that can be used with fillStyle and strokeStyle
      var i = 0;
      var funcreturn;

      function rndNumForHere() {
        //this gets called often, so we might as well have a separate function to clean things up a bit
        return randomThing([[0,"0",.5,1,-.5,-1], numbers, rnd(1000), rndr()]);
      }

      switch (rnd(9)) {
        case 0:
          funcreturn = "function(ctx){/*create a linear gradient*/" +
            "var grad = ctx.createLinearGradient(" +
            rndNumForHere() + "," +
            rndNumForHere() + "," +
            rndNumForHere() + "," +
            rndNumForHere() + ");" +
            "/*add some colors to the gradient*/";
            for (i=0;i<rnd(10);i++)
            {
              funcreturn += "  try{" +
              "    grad.addColorStop(" +
                    randomThing([0, '0', .5, 1, -.5, -1, numbers, rndr()]) + "," +
                    randomThing(colors) +
                  ");" +
              "  }catch(Exx2){}";
            }
            funcreturn += "return grad; }(" + myContext + ")";
          return funcreturn;

        case 1:
            funcreturn = "function(ctx){/*create a radial gradient*/" +
            "var grad = ctx.createRadialGradient(" +
            rndNumForHere() + "," +
            rndNumForHere() + "," +
            rndNumForHere() + "," +
            rndNumForHere() + "," +
            rndNumForHere() + "," +
            rndNumForHere() + ");" +
            "/*add some colors to the gradient*/";
            for (i=0;i<rnd(10);i++)
            {
              funcreturn += "  try{" +
              "    grad.addColorStop(" +
                    randomThing([0, '0', .5, 1, -.5, -1, numbers, rndr()]) + "," +
                    randomThing(colors) + ");" +
              "  }catch(Exx2){}";
            }
            funcreturn += "return grad; }(" + myContext + ")";
          return funcreturn;

        case 2:
          //return a repeating pattern
          return "function(ctx){return ctx.createPattern(" +
            randomThing(inputImages) + ",'" +
            randomThing(["repeat","repeat-x","repeat-y","no-repeat"]) + "');}(" + myContext + ")";

        default:
          return randomThing(colors);
      }
    }


    // Attributes on CanvasRenderingContext2D
    // https://developer.mozilla.org/en/DOM/CanvasRenderingContext2D#Attributes
    // XXX https://developer.mozilla.org/en/DOM/CanvasRenderingContext2D#Gecko-specific_attributes
    // XXX some of these are strings, some of them are not. are they all getting escaped?
    var attributes = {
      "fillStyle": CreateStyle,
      "font": function() { return simpleSource(randomThing(fuzzValues.numbersWithUnits) + " " + randomThing(fuzzValues.fontFaces)); },
      "globalAlpha": numbersZeroOne,
      "globalCompositeOperation": ["'copy'", "'darker'", "'destination-atop'", "'destination-in'", "'destination-out'", "'destination-over'", "'lighter'", "'source-atop'", "'source-in'", "'source-out'", "'source-over'", "'xor'"],
      "lineCap": ["'butt'", "'round'", "'square'"],
      "lineJoin": ["'round'", "'bevel'", "'miter'"],
      "lineWidth": numbers,
      "miterLimit": numbers,
      "shadowBlur": numbers,
      "shadowColor": colors,
      "shadowOffsetX": numbers,
      "shadowOffsetY": numbers,
      "strokeStyle": CreateStyle,
      "textAlign": ["'start'", "'end'", "'left'", "'right'", "'center'"],
      "textBaseLine": ["'top'", "'hanging'", "'middle'", "'alphabetic'", "'ideographic'", "'bottom'"],
    };
    var allattribs = getKeysFromHash(attributes);

    // Methods on CanvasRenderingContext2D
    // https://developer.mozilla.org/en/DOM/CanvasRenderingContext2D
    // http://www.whatwg.org/specs/web-apps/current-work/multipage/the-canvas-element.html#2dcontext
    /*
    method layout:
    "name": [arg values, arg values, ...]
    */
    var methods = {
      "restore": [],
      "rotate": [numbers],
      "save": [],
      "scale": [numbers, numbers],
      "translate": [numbers, numbers],
      "arc": [numbers, numbers, numbers, numbers, numbers, [1, 0]],
      "arcTo": [numbers, numbers, numbers, numbers, numbers],
      "bezierCurveTo": [numbers, numbers, numbers, numbers, numbers, numbers],
      "beginPath": [],
      "clip": [],
      "closePath": [],
      "lineTo": [numbers, numbers],
      "moveTo": [numbers, numbers],
      "quadraticCurveTo": [numbers, numbers, numbers, numbers],
      "rect": [numbers, numbers, numbers, numbers],
      "stroke": [],
      "strokeRect": [numbers, numbers, numbers, numbers],
      "strokeText": [texts, numbers, numbers, numbers],
      "clearRect": [numbers, numbers, numbers, numbers],
      "fill": [],
      "fillRect": [numbers, numbers, numbers, numbers],
      "fillText": [texts, numbers, numbers, numbers],
      "createLinearGradient": [numbers, numbers, numbers, numbers],
      "createPattern": [inputImages, ["'repeat'", "'repeat-x'", "'repeat-y'", "'no-repeat'"]],
      "createRadialGradient": [numbers, numbers, numbers, numbers, numbers, numbers],
      "drawImage": [inputImages, numbers, numbers, numbers, numbers, numbers, numbers, numbers, numbers],
      "scrollPathIntoView": [],
      "setTransform": [numbers, numbers, numbers, numbers, numbers, numbers],
      "transform": [numbers, numbers, numbers, numbers, numbers, numbers],
      "isPointInPath": [numbers, numbers],
      "measureText": [texts]
    };
    var allmethods = getKeysFromHash(methods);

    // Missing: createImageData (which has two forms!), getImageData, putImageData
    // Missing: canvas.toDataURL

  return { makeCommand: makeCommand };
})();


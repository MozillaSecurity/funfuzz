const NUM_MATH_FUNCTIONS = 6;

var binaryMathOps = [
  " * ", " / ", " % ", " + ", " - ", " << ", " >> ", " >>> ",
  " < ", " > ", " <= ", " >= ",
  " == ", " != ",
  " === ", " !== ",
  " & ", " | ", " ^ ", " && ", " || ",
  " , ",
];

var leftUnaryMathOps = [
  " ! ", " + ", " - ", " ~ ",
];

var unaryMathFunctions = [
  "abs",
  "acos",
  "acosh",
  "asin",
  "asinh",
  "atan",
  "atanh",
  "cbrt",
  "ceil",
  "cos",
  "cosh",
  "exp",
  "expm1",
  // "floor", // avoid breaking rnd.
  "/*NODIFF*/fround", // bug 946679
  "log",
  "log2",
  "log10",
  "log1p",
  // "random", // avoid breaking rnd. avoid non-determinism.
  "round",
  "sign",
  "sin",
  "sinh",
  "sqrt",
  "tan",
  "tanh",
  "trunc",
];

// n-ary functions will also be tested with varying numbers of parameters by makeFunction
var binaryMathFunctions = [
  "atan2",
  "hypot", // n-ary
  "imul",
  "max", // n-ary
  "min", // n-ary
  "pow",
];

function generateMathFunction(d, b, i)
{
  return "(function(x, y) { " + directivePrologue() + "return " + generateMathExpr(d, b, i) + "; })"
}

function generateMathExpr(d, b, i)
{
  // As depth decreases, make it more likely to bottom out
  if (d < rnd(5)) {
    if (rnd(4)) {
      return Random.index(["x", "y"]);
    }
    return Random.index(numericVals);
  }

  if (rnd(500) == 0)
    return makeExpr(d - 1, b);

  function r() { return generateMathExpr(d - 1, b, i); }

  // Frequently, coerce both the inputs and outputs to the same "numeric sub-type"
  // (asm.js formalizes this concept, but JITs may have their own variants)
  var commonCoercion = rnd(10);
  function mc(expr) {
    switch(rnd(3) ? commonCoercion : rnd(10)) {
      case 0: return "(" + " + " + expr + ")";     // f64 (asm.js)
      case 1: return "/*NODIFF*/Math.fround(" + expr + ")";  // f32 // bug 946679
      case 2: return "(" + expr + " | 0)";         // i32 (asm.js)
      case 3: return "(" + expr + " >>> 0)";       // u32
      default: return expr;
    }
  }

  if (i > 0 && rnd(10) == 0) {
    // Call a *lower-numbered* mathy function. (This avoids infinite recursion.)
    return mc("mathy" + rnd(i) + "(" + mc(r()) + ", " + mc(r()) + ")");
  }

  if (rnd(20) == 0) {
    return mc("(" + mc(r()) + " ? " + mc(r()) + " : " + mc(r()) + ")");
  }

  switch(rnd(4)) {
    case 0:  return mc("(" + mc(r()) + Random.index(binaryMathOps) + mc(r()) + ")");
    case 1:  return mc("(" + Random.index(leftUnaryMathOps) + mc(r()) + ")");
    case 2:  return mc("Math." + Random.index(unaryMathFunctions) + "(" + mc(r()) + ")");
    default: return mc("Math." + Random.index(binaryMathFunctions) + "(" + mc(r()) + ", " + mc(r()) + ")");
  }
}



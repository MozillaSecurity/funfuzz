"use strict";

module.exports = {
  "parserOptions": {
      "ecmaVersion": 2018,
  },
  "rules": {
    // Adapted from m-c rev 440407:2d2dee08739f (Fx64) tools/lint/eslint/.eslintrc.js
    "camelcase": "error",
    "curly": ["error", "multi-line"],
    "handle-callback-err": ["error", "er"],
    "indent": ["error", 2, {"SwitchCase": 1}],
    // Replaced by the "indent" rule
    // "indent-legacy": ["error", 2, {"SwitchCase": 1}],
    "linebreak-style": ["error", "unix"],
    "max-len": ["error", 120, 2],
    // Multiple empty lines can sometimes help readability
    // "no-multiple-empty-lines": ["error", {"max": 1}],
    "no-shadow": "error",
    "no-undef": ["error", {"typeof": true}],
    "no-undef-init": "error",
    // We want to test object-curly-spacing in funfuzz
    "object-curly-spacing": "off",
    // Turned off until we are ready to refactor jsfunfuzz
    // There are multiple areas where we deliberately split up strings to avoid the harness searching jsfunfuzz itself
    "no-useless-concat": "off",
    // object-shorthand requires to be fully on ES6+
    "object-shorthand": "off",
    "one-var": ["error", "never"],
    "operator-linebreak": ["error", "after"],
    "quotes": ["error", "double"],
    "semi": ["error", "always"],
    // jsfunfuzz turns strict mode on and off
    // "strict": ["error", "global"],
  }
};

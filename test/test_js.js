// Copyright (c) 2026, Brookhaven Science Associates, LLC
// SPDX-License-Identifier: Apache-2.0
//
// Sanity checks for the generated JavaScript module.  Run: node test/test_js.js
"use strict";
const assert = require("assert");
const path = require("path");
const u = require(path.join(__dirname, "..", "js", "hep-units.js"));

const close = (a, b) => Math.abs(a - b) <= 1e-9 * (1 + Math.abs(b));

// Named values.
assert.strictEqual(u.cm, 10);
assert.strictEqual(u.m, 1000);
assert.strictEqual(u.mm, 1);
assert.strictEqual(u.ns, 1);
assert.strictEqual(u.eplus, 1);
assert.ok(close(u.degree, Math.PI / 180));
assert.ok(close(u.twopi, 2 * Math.PI));
assert.ok(close(u.c_light, 299.792458));
assert.strictEqual(u.V, u.volt);                   // aliases are properties
assert.strictEqual(u.NAMES.length, Object.keys(u.TABLE).length);
assert.ok(Object.isFrozen(u) && Object.isFrozen(u.TABLE));

// Import and export.
const len = 1.5 * u.cm;
assert.strictEqual(len, 15);
assert.strictEqual(len / u.cm, 1.5);

// parse().
assert.strictEqual(u.parse("1.5*cm"), 15);
assert.strictEqual(u.parse("1.5 cm"), 15);
assert.strictEqual(u.parse("2*pi"), u.twopi);
assert.ok(close(u.parse("9.8 m/s^2"), 9.8 * u.m / (u.s * u.s)));
assert.strictEqual(u.parse("2 cm + 3 mm"), 23);
assert.strictEqual(u.parse("-2^2"), -4);
assert.strictEqual(u.parse("2^3^2"), 512);
assert.strictEqual(u.parse("0.5*k", { k: 0.015 }), 0.5 * 0.015);
assert.strictEqual(u.parse("0.5*k", new Map([["k", 0.015]])), 0.5 * 0.015);
assert.strictEqual(u.parse("2*V", { V: 7 }), 14);   // caller symbols shadow

// Errors, including names inherited from Object.prototype.
for (const bad of ["", "1 +", "(1", "1)", "furlong", "foo(1)", "sqrt(1, 2)",
                   "1 $ 2", ".", "toString", "constructor", "__proto__",
                   "hasOwnProperty(1)"]) {
  assert.throws(() => u.parse(bad), /^Error: hep_units\.parse: /, bad);
}
assert.throws(() => u.parse(42), TypeError);

console.log("ok");

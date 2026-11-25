// Copyright (c) 2026, Brookhaven Science Associates, LLC
// SPDX-License-Identifier: Apache-2.0
//
// Read lines "expression|name=value;name=value" from stdin and print, per
// line, hepUnits.parse()'s value as a shortest round-trip decimal (exact),
// or "error".  Used by test_parity.py to compare JavaScript with C++, Python
// and Jsonnet.
"use strict";
const path = require("path");
const u = require(path.join(__dirname, "..", "js", "hep-units.js"));

const lines = require("fs").readFileSync(0, "utf8").split("\n");
if (lines.length && lines[lines.length - 1] === "") { lines.pop(); }
const out = [];
for (const line of lines) {
  const bar = line.indexOf("|");
  const expr = bar < 0 ? line : line.slice(0, bar);
  const symbols = {};
  if (bar >= 0) {
    for (const kv of line.slice(bar + 1).split(";")) {
      const eq = kv.indexOf("=");
      if (eq >= 0) { symbols[kv.slice(0, eq)] = Number(kv.slice(eq + 1)); }
    }
  }
  try {
    out.push(String(u.parse(expr, symbols)));
  } catch (err) {
    out.push("error");
  }
}
process.stdout.write(out.join("\n") + (out.length ? "\n" : ""));

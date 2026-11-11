// Copyright (c) 2026, Brookhaven Science Associates, LLC
// SPDX-License-Identifier: Apache-2.0
// Sanity checks for the generated Jsonnet library.
// Evaluates to "ok" when all assertions pass; errors otherwise.
local u = import 'hep/units.libsonnet';

local close(a, b) = std.abs(a - b) <= 1e-9 * (1.0 + std.abs(b));

assert u.cm == 10.0 : 'cm';
assert u.m == 1000.0 : 'm';
assert u.mm == 1.0 : 'mm';
assert u.eplus == 1.0 : 'eplus';
assert close(u.degree, u.pi / 180.0) : 'degree';
assert close(u.twopi, 2 * u.pi) : 'twopi';

assert u.parse('1.5*cm') == 15.0 : 'parse 1.5*cm';
assert u.parse('1.5 cm') == 15.0 : 'parse 1.5 cm';
assert u.parse('cm') == u.cm : 'parse cm';
assert u.parse('2*pi') == u.twopi : 'parse 2*pi';
assert u.parse('eplus') == 1.0 : 'parse eplus';

assert close(u.parse('9.8 m/s^2'), 9.8 * u.m / (u.s * u.s)) : 'parse 9.8 m/s^2';
assert close(u.parse('1.6 mm/us'), 1.6 * u.mm / u.us) : 'parse 1.6 mm/us';
assert close(u.parse('3 mm*ns'), 3 * u.mm * u.ns) : 'parse 3 mm*ns';

assert close(u.parse('0.5*0.02'), 0.01) : 'parse 0.5*0.02';
assert u.parse('(1+2)*mm') == 3.0 : 'parse (1+2)*mm';
assert u.parse('2 cm + 3 mm') == 23.0 : 'parse 2 cm + 3 mm';
assert u.parse('-2^2') == -4.0 : 'parse -2^2';
assert close(u.parse('s^-1'), 1.0 / u.s) : 'parse s^-1';
assert u.parse('1.e3') == 1000.0 : 'parse 1.e3';
assert u.parse('.5') == 0.5 : 'parse .5';
assert u.parse('sqrt(4)') == 2.0 : 'parse sqrt(4)';
assert close(u.parse('0.5*kWireDiam', { kWireDiam: 0.015 }), 0.0075) : 'parse with symbols';
assert u.parse('m', { m: 5 }) == 5 : 'symbols shadow units';

assert std.length(std.objectFields(u.table)) > 100 : 'table size';
assert u.table.cm == u.cm : 'table cm';

'ok'

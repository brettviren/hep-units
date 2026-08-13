// Sanity checks for the generated Jsonnet library.
// Evaluates to "ok" when all assertions pass; errors otherwise.
local u = import 'dune/units.libsonnet';

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

assert std.length(std.objectFields(u.table)) > 100 : 'table size';
assert u.table.cm == u.cm : 'table cm';

'ok'

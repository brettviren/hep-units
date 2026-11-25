# hep-units in Jsonnet

The Jsonnet product is one library file, `jsonnet/hep/units.libsonnet`.  It is
an object whose hidden fields are the units and constants, plus a `parse()`
function written in pure Jsonnet.  It works with go-jsonnet, the C++ jsonnet
and the Python `_jsonnet` binding.

## Getting it

Put the directory that holds `hep/` on the Jsonnet library path: the
source tree's `jsonnet/`, or `<prefix>/share/jsonnet` after a CMake install.

```bash
jsonnet -J <prefix>/share/jsonnet config.jsonnet
# or: export JSONNET_PATH=<prefix>/share/jsonnet
```

```jsonnet
local u = import 'hep/units.libsonnet';
```

All fields are hidden (`::`), so `u` itself manifests as `{}` and can never
leak a table of units into your output.

## Names

```jsonnet
u.mm  u.cm  u.m  u.km          // length; u.mm == 1
u.ns  u.us  u.ms  u.s          // time;   u.ns == 1
u.eV  u.MeV  u.GeV             // energy; u.MeV == 1
u.eplus  u.coulomb             // charge; u.eplus == 1
u.volt  u.kilovolt  u.tesla
u.rad  u.deg
u.pi  u.c_light  u.hbarc  u.k_Boltzmann  ...
u.V  u.kV  u.atm  u.micron     // aliases (Geant4 evaluator names)
```

## Import: multiply

```jsonnet
local u = import 'hep/units.libsonnet';
local length = 10 * u.cm;
local speed = 1.6 * u.mm / u.us;
{
  length: length,            // 100
  speed: speed,              // 0.0016
  time: length / speed,      // 62500
}
```

## JSON output and the units firewall

The JSON that Jsonnet writes carries numbers **in the system of units**.  That
is exactly right when the program reading the JSON uses the same system,
for example a C++ program built with `hep/units.hpp` or a Python one using
`hep_units`: the numbers cross with no conversion and the program uses them
directly.  This is the main reason hep-units gives Jsonnet the same values, bit
for bit, as the other languages.

When the reader uses another convention, the JSON is a
[units firewall](philosophy.md#the-units-firewall) and you must export, either
in the Jsonnet or in the reader.  Exporting in Jsonnet keeps the reader
simple; put the unit in the key so the file says what it means:

```jsonnet
{
  length_cm: length / u.cm,          // 10
  drift_time_us: (length / speed) / u.us,   // 62.5
}
```

## Export: divide

To show a value to people, divide and format:

```jsonnet
'drift time %g us' % [(length / speed) / u.us]   // "drift time 62.5 us"
std.toString(length / u.cm) + ' cm'              // "10 cm"
```

## Import from text: `parse()`

```jsonnet
u.parse(text, symbols={})
```

```jsonnet
u.parse('1.6 mm/us')         // 0.0016
u.parse('500 V/cm')          // 5e-05
u.parse('9.8 m/s^2')         // 9.8e-15
u.parse('2 cm + 3 mm')       // 23
```

**Caller symbols** are an object, looked up before the table:

```jsonnet
u.parse('kTPCWidth/2 + 1*mm', { kTPCWidth: 10 * u.cm }) / u.mm    // 51
```

**Values from the command line.**  External variables and top-level arguments
are strings, so `parse()` imports them, units and all:

```jsonnet
// jsonnet -J ... -V pitch="5 mm" -V field="0.5 kV/cm" detector.jsonnet
{
  pitch: u.parse(std.extVar('pitch')),       // 5
  field: u.parse(std.extVar('field')),       // 5e-05
}
```

```jsonnet
// jsonnet -J ... --tla-str length="2 m" job.jsonnet
function(length='1 m') { length: u.parse(length) }
```

**Export to a unit named in text:**

```jsonnet
u.parse('500 V/cm') / u.parse('kV/cm')     // 0.5
```

**Errors** stop evaluation with a runtime error whose message starts
`hep_units.parse:`:

```
RUNTIME ERROR: hep_units.parse: unknown unit 'furlong' at column 2 of "3 furlong"
```

Jsonnet has no way to catch an error, so check untrusted text elsewhere, or
make sure every name it uses is known (`std.objectHas(u.table, name)`).

## The table

```jsonnet
u.names            // array of every symbol name, in definition order (229)
u.table            // object { name: value } of every symbol
u.table['cm']      // 10
std.objectHas(u.table, 'furlong')   // false
```

`u.resolve(atom)` is an older helper that returns the value of a single number
or name (`u.resolve('cm')` is 10).  It is kept for compatibility; use
`parse()` in new code.

## Speed

`parse()` is written in Jsonnet, which is slow at string processing compared
with a compiled language.  It is fine for configuration values, even many
hundreds of them.  For a large table of numbers that share one unit, parse the
unit once and multiply:

```jsonnet
local cm = u.parse(unit_text);
[x * cm for x in numbers]
```

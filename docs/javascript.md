# hep-units in JavaScript

The JavaScript product is one file, [`js/hep-units.js`](../js/hep-units.js),
with no dependencies.  It holds every unit and constant as a `const`, the
lookup table, and `parse()`.  It runs in any browser and in Node.js, Deno and
Bun.

**Try it:** the [live demo](demo.html) runs `parse()` in your browser.

<!-- demo -->

## Getting it

The file is a UMD module, so one file serves every way of loading it:

```html
<!-- Browser, classic script: defines the global `hepUnits`.  Also works
     from file://, where ES modules do not load. -->
<script src="hep-units.js"></script>
<script>
  const u = hepUnits;
  console.log(u.parse("1.5 cm"));    // 15
</script>
```

```javascript
// Node.js or Bun, CommonJS
const u = require("./hep-units.js");

// Node.js or Bun, ES module: the module object is the default export
import u from "./hep-units.js";
```

Where a `.js` file is always an ES module and CommonJS is not emulated
(Deno, and `<script type="module">` in a browser), the file defines the
global instead.  Import it for that effect:

```javascript
import "./hep-units.js";
const u = globalThis.hepUnits;
```

With npm, the hep-units source tree is a package whose `main` is this file:

```bash
npm install /path/to/hep-units      # then: const u = require("hep-units");
```

A CMake install puts the file in `<prefix>/share/javascript/hep-units.js`.

The module object is frozen: no unit can be reassigned by accident.

## Names

```javascript
u.mm  u.cm  u.m  u.km          // length; u.mm === 1
u.ns  u.us  u.ms  u.s          // time;   u.ns === 1
u.eV  u.MeV  u.GeV             // energy; u.MeV === 1
u.eplus  u.coulomb             // charge; u.eplus === 1
u.volt  u.kilovolt  u.tesla
u.rad  u.deg
u.pi  u.c_light  u.hbarc  u.k_Boltzmann  ...
u.V  u.kV  u.atm  u.micron     // aliases (Geant4 evaluator names)
```

Destructure the names you use:

```javascript
const { cm, mm, us, kilovolt } = hepUnits;
```

Each value is bit-identical to the C++, Python and Jsonnet ones; the test
suite checks all 229 names.

## Import: multiply

```javascript
const length = 10 * u.cm;            // 100   (mm)
const speed = 1.6 * u.mm / u.us;     // 0.0016 (mm/ns)
const field = 500 * u.volt / u.cm;   // 0.00005

const time = length / speed;         // 62500 (ns)
```

## Export: divide

```javascript
console.log(`drift time ${time / u.us} us`);              // drift time 62.5 us
console.log(`field ${field / (u.kilovolt / u.cm)} kV/cm`); // field 0.5 kV/cm
```

In a web page the same rule holds for anything shown to people: divide by the
unit you display, and display the unit.

```javascript
element.textContent = `${(time / u.us).toPrecision(4)} µs`;
```

## Import from text: `parse()`

```javascript
u.parse(text, symbols)   // -> number
```

```javascript
u.parse("1.6 mm/us");        // 0.0016
u.parse("500 V/cm");         // 0.00005
u.parse("9.8 m/s^2");        // 9.8e-15
u.parse("2 cm + 3 mm");      // 23
```

**Caller symbols** are a plain object or a `Map`, looked up before the table.
Only an object's *own* properties count, so `toString` or `constructor` can
never be picked up from a prototype:

```javascript
u.parse("kTPCWidth/2 + 1*mm", { kTPCWidth: 10 * u.cm }) / u.mm;     // 51
u.parse("half*m", new Map([["half", 0.5]])) / u.cm;                 // 50
```

**Form input** is the typical text boundary in a browser.  `parse()` is the
[firewall](philosophy.md#the-units-firewall) between what people type and
the numbers your code uses:

```javascript
input.addEventListener("change", () => {
  try {
    const pitch = u.parse(input.value);           // "5 mm", "0.5 cm", ...
    output.textContent = `${pitch / u.mm} mm`;
  } catch (err) {
    output.textContent = err.message;
  }
});
```

**Export to a unit named in text:**

```javascript
speed / u.parse("cm/us");    // 0.16
```

**Errors** throw an `Error` whose message starts `hep_units.parse:`, and a
non-string `text` throws a `TypeError`:

```javascript
try {
  u.parse("3 furlong");
} catch (err) {
  console.log(err.message);
  // hep_units.parse: unknown unit 'furlong' at column 9 of "3 furlong"
}
```

## The table

```javascript
u.NAMES                 // frozen array of every symbol name, in definition order
u.TABLE                 // frozen object { name: value }
u.NAMES.length          // 229 with the default files
u.NAMES.filter(n => u.TABLE[n] === u.cm)    // ["centimeter", "cm"]
```

## The file

The file is generated from the [system-of-units files](units-files.md) and,
like the other products, keeps each definition's structure, with the value in
a comment:

```javascript
  const millimeter = 1.;  // = 1.0
  const centimeter = 10. * millimeter;  // = 10.0
  const cm = centimeter;  // = 10.0
  const volt = 1.e-6 * megavolt;  // = 1e-06
```

<!-- include: ../js/hep-units.js -->

# hep-units

The CLHEP **HEP System of Units** — plus local additions (units not in CLHEP)
and constants of nature — provided as three interchangeable products generated
from a single source of truth:

| Product | File | Consume as |
| ------- | ---- | ---------- |
| C++ header | `include/hep/units.hpp` | `#include "hep/units.hpp"` → `hep::units::cm`, `hep::units::parse(...)` |
| Python module | `src/hep_units/__init__.py` | `import hep_units as u` → `u.cm`, `u.parse(...)` |
| Jsonnet library | `jsonnet/hep/units.libsonnet` | `local u = import 'hep/units.libsonnet';` → `u.cm`, `u.parse(...)` |

All three carry identical numeric values (IEEE-754 doubles, verified
bit-for-bit) and the same set of 166 named symbols, so a length written as
`1.5*cm` means the same thing in C++, Python and Jsonnet.

Each product keeps the **structure** of every definition rather than a
flattened number — e.g. the C++ header has `inline constexpr double cm2 =
cm*cm;`, Python has `cm2 = cm*cm`, Jsonnet has `cm2:: self.cm * self.cm` — with
the resolved value in a trailing comment. Because the three languages share
operator precedence, left-associativity and `double` semantics, this is exactly
equivalent to the flattened form while letting a reader see how each unit is
built up.

## Single source of truth

The values live in human-editable `.units` files under `units/`:

- **`units/clhep.units`** — a faithful, line-by-line transcription of
  [`CLHEP/Units/SystemOfUnits.h`](https://github.com/Geant4/geant4/blob/master/source/externals/clhep/include/CLHEP/Units/SystemOfUnits.h).
  **Do not edit** — it is meant to mirror CLHEP exactly.

- **`units/hep.units`** — the place to add units CLHEP does not provide and any
  constants of nature. It is consumed *after* `clhep.units`, so it may reference
  any CLHEP symbol.

- **`units/evaluator.units`** — *aliases*: the 63 names that the CLHEP
  expression evaluator (`HepTool::Evaluator::setSystemOfUnits`, used by
  Geant4's GDML reader) knows but `SystemOfUnits.h` lacks, such as `V`, `kV`,
  `A`, `T`, `atm`, `micron`, `litre`. Each is defined from the CLHEP name for
  the same unit and takes its exact value. With them, `parse()` accepts every
  unit a GDML file may use (DUNE files write `Efield` auxiliaries as
  `500*V/cm`).

### `.units` format

```
# Blank lines and lines starting with '#' are ignored.

@section Length [L]        # a grouping label for the output (optional)
@kind unit                 # tag following defs: 'unit' (default), 'constant' or 'alias'

millimeter  = 1.           # NAME = EXPRESSION
centimeter  = 10.*millimeter
meter       = 1000.*millimeter   # trailing comments after '#' are allowed
```

- `NAME` is a C/Python identifier.
- `EXPRESSION` is simple arithmetic — `+ - * /`, parentheses, unary `+/-` — over
  numeric literals and **previously defined** names. Definitions are evaluated
  top-to-bottom; files are consumed in the order given, so each name must be
  defined before it is used.
- `**` (power) is accepted only with an **integer** exponent; the generator
  expands it to repeated multiplication (`x**2` → `x*x`) so the output stays
  valid `constexpr` C++ and bit-identical across languages. Prefer writing the
  multiplication out (e.g. `c_squared = c_light*c_light`).
- Every defined symbol (units and constants alike) becomes a named value in each
  product and an entry in that product's lookup table.
- Symbols of kind `alias` are in every lookup table, so `parse()` knows them,
  but are kept out of the way of short names in user code: in C++ they are in
  the nested namespace `hep::units::aliases` (`hep::units::aliases::V`), so
  `using namespace hep::units` does not import `A C F H K N S T V W`; in
  Python they are module attributes but not in `__all__`; in Jsonnet they are
  hidden fields like every unit. Only aliases may refer to aliases.

## The `parse()` function

Each product includes a `parse()` that evaluates an arithmetic expression of
numbers, units and constants to a number in the system of units:

```
parse("1.5*cm")         ->  15.0        // explicit multiply
parse("1.5 cm")         ->  15.0        // whitespace = implicit multiply
parse("9.8 m/s^2")      ->  9.8e-15
parse("2*pi")           ->  6.2831853…
parse("0.5*0.02")       ->  0.01        // plain arithmetic, e.g. GDML attributes
parse("2 cm + 3 mm")    ->  23.0
parse("(1+2)*mm")       ->  3.0
parse("s^-1")           ->  1e-09
parse("sqrt(2)*cm")     ->  14.142135…
parse("0.5*kWireDiam", {"kWireDiam": 0.015})   ->  0.0075   // caller symbols
```

Grammar, lowest to highest precedence:

```
expr    := term { ('+' | '-') term }
term    := unary { ('*' | '/' | <whitespace>) unary }
unary   := ('+' | '-') unary | power
power   := primary [ ('^' | '**') unary ]          (right-associative)
primary := number | name | name '(' expr {',' expr} ')' | '(' expr ')'
```

- Two operands side by side multiply, so `"1.5 cm"` is `1.5*cm` and
  `"9.8 m/s^2"` is `9.8*m/(s^2)`.  `^` binds tighter than a sign:
  `"-2^2"` is -4; `"2^3^2"` is 512.
- Numbers are C-style: `1`, `1.`, `.5`, `1.5e-3`, `1.E3` (in all three
  products; Jsonnet no longer needs JSON-only literals).
- Names are looked up first in the caller's symbols, then in the table.  This
  is how a GDML reader evaluates attributes that use its file's
  `<constant>`s.  C++: `parse(text, std::unordered_map<std::string,double>)`
  or `parse_with(text, lookup)` where `lookup(std::string_view)` returns a
  `const double*` (nullptr when unknown); Python: `parse(text, mapping)`;
  Jsonnet: `parse(text, object)`.
- Functions: `sqrt sin cos tan asin acos atan exp log pow abs min max`.
- Errors (unknown name or function, bad syntax, empty text) throw
  `std::invalid_argument` / raise `ValueError` / are Jsonnet errors.
- Arithmetic gives bit-identical results in C++, Python and Jsonnet
  (`test/test_parity.py` checks every case of `test/parse-cases.txt`).
  Functions use each language's math library and may differ in the last bit
  (seen: `acos(0.3)` in go-jsonnet).
- The grammar is a superset of the previous flat product/quotient one, and
  every expression that one accepted gives the same value.

## Regenerating the products (developers only)

The generated files are **committed** to the repository, so downstream builds
never run the generator and it introduces **no build-time dependency** — it uses
only the Python standard library.

Regenerate after editing a `.units` source:

```bash
python generate/generate.py
# or, from a CMake build tree:
cmake --build build --target regenerate
```

## Building and installing

### CMake (C++ header + Python file + Jsonnet library)

```bash
cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/some/prefix
cmake --build build
ctest --test-dir build          # runs the C++, Python and Jsonnet checks
cmake --install build
```

Installs:

```
<prefix>/include/hep/units.hpp
<prefix>/python/hep_units/__init__.py          # add <prefix>/python to PYTHONPATH
<prefix>/share/jsonnet/hep/units.libsonnet     # add <prefix>/share/jsonnet to -J path
<prefix>/lib/cmake/hep_units/…                 # find_package(hep_units)
```

Downstream C++:

```cmake
find_package(hep_units REQUIRED)
target_link_libraries(myapp PRIVATE hep_units::hep_units)
```

### pyproject.toml (Python module only)

A parallel, packaging-native install of the same single Python file:

```bash
pip install .          # or: uv tool install -e .
python -c "import hep_units as u; print(u.parse('1.6 mm/us'))"
```

## Layout

```
units/clhep.units             source of truth: CLHEP SystemOfUnits.h (frozen)
units/hep.units               source of truth: extra units + constants of nature
units/evaluator.units         source of truth: CLHEP evaluator / GDML aliases
generate/generate.py          the source-code generator (developer tool)
include/hep/units.hpp         GENERATED C++ header
src/hep_units/__init__.py     GENERATED Python module
jsonnet/hep/units.libsonnet   GENERATED Jsonnet library
CMakeLists.txt                 build/install for all three products
pyproject.toml                 parallel Python install
test/                          C++, Python and Jsonnet checks (ctest + pytest);
                               parse-cases.txt is shared, test_parity.py
                               compares the three products
```

## License

Copyright (c) 2026, Brookhaven Science Associates, LLC.
Licensed under the Apache License, Version 2.0 (SPDX: `Apache-2.0`); see the
[LICENSE](LICENSE) file. The `units/clhep.units` source transcribes CLHEP's
`SystemOfUnits.h` (CLHEP is itself distributed under a permissive HEP license).

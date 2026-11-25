# System-of-units files

A hep-units system of units is defined in plain text, in `.units` files.  A
developer tool, `generate/generate.py`, reads them and writes the four
products: the C++ header, the Python module, the Jsonnet library and the
JavaScript module.  The products are committed to the repository, so users
of hep-units never run the generator; it is needed only to change or extend
the system.

## The default system

The default system is three files, read in this order:

| File                    | Holds                                                     | Edit?  |
| ----------------------- | --------------------------------------------------------- | ------ |
| `units/clhep.units`     | a line-by-line transcription of CLHEP's `SystemOfUnits.h` | no: it mirrors CLHEP |
| `units/hep.units`       | units CLHEP lacks (`inch`, `week`, `erg`, ...) and constants of nature (`c_light`, `hbarc`, ...) | yes |
| `units/evaluator.units` | aliases: names Geant4's expression evaluator (and so GDML) knows but CLHEP's header lacks (`V`, `kV`, `atm`, ...) | only to follow Geant4 |

Regenerate after editing any of them:

```bash
python generate/generate.py
# or, from a CMake build tree:
cmake --build build --target regenerate
```

## The format

```
# -*- mode: conf -*-
# Blank lines and lines starting with '#' are ignored.

@section Length [L]            # a label for the definitions that follow
@kind unit                     # 'unit' (the default), 'constant' or 'alias'

millimeter  = 1.               # NAME = EXPRESSION
centimeter  = 10.*millimeter
meter       = 1000.*millimeter # a comment may follow a definition
mm          = millimeter
cm2         = cm*cm            # or: cm**2
```

**Definitions.**  `NAME = EXPRESSION`, one per line.

- `NAME` is a C/Python identifier (letters, digits, `_`; not starting with a
  digit).  It must be new: a name may be defined only once across all files.
- `EXPRESSION` is arithmetic over numeric literals and names **defined
  earlier** (in this file or an earlier one): `+ - * /`, parentheses and
  unary `+ -`.
- `**` (power) is allowed only with an integer literal exponent
  (`cm**2`, `s**-1`).  The generator writes it out as repeated
  multiplication, so the products stay valid `constexpr` C++ and agree
  bit for bit.
- The expression syntax here is deliberately smaller than the
  [`parse()` language](parse.md): no implicit multiplication, no `^`, no
  functions.

**Directives.**

- `@section TEXT` labels the following definitions.  The label becomes a
  comment heading in each product.  It does not change any value.
- `@kind unit|constant|alias` tags the following definitions:
  - `unit` and `constant` are treated alike, except that each product groups
    them under different headings.
  - `alias` is for alternative spellings that should be known to `parse()`
    but kept out of the way in code.  Aliases are put in the C++ namespace
    `hep::units::aliases`, left out of the Python module's `__all__`, and
    exposed normally in Jsonnet and JavaScript.  Only an alias may refer to
    an alias.
- `@section` and `@kind` **reset at the start of each file**: every file
  starts as `@kind unit` with no section.

**Values.**  Every definition is evaluated in Python `float` (IEEE-754
`double`) as it is read.  The generator writes each product's definition with
the same structure (`cm2 = cm * cm`) rather than as a flat number.  C++,
Python, Jsonnet and JavaScript share the precedence, associativity and
`double` arithmetic involved, so all four compute identical values; the test
suite checks this.

**The base units** are whatever names you define as `1.`.  In the default
system those are `millimeter`, `nanosecond`, `megaelectronvolt`, `eplus`,
`kelvin`, `mole`, `candela` and `radian`.  Nothing else in hep-units depends
on which units those are.

## Extending the system with more files

To add your own units or constants, write them in a new file and pass it with
`--extra` (repeatable).  Extra files are read after the default ones and may
use any name defined there:

```
# lartpc.units: local additions for a liquid-argon TPC project.
@section Charge (LArTPC)
femtocoulomb = 1.e-15*coulomb
fC = femtocoulomb

@section Electronics
millivolt = 1.e-3*volt
mV = millivolt
mV_per_fC = mV/fC

@kind constant
@section Liquid argon
W_ion_LAr = 23.6*eV
LAr_density = 1.39*g/cm3
```

```bash
python generate/generate.py --extra lartpc.units \
    --hpp    myproject/include/hep/units.hpp \
    --py     myproject/python/hep_units/__init__.py \
    --jsonnet myproject/jsonnet/hep/units.libsonnet \
    --js     myproject/js/hep-units.js
```

The result is the default system plus your seven names, in all four languages,
including `parse()`:

```python
import hep_units as u            # the extended module
u.parse("14 mV/fC") / u.mV_per_fC     # 14.0
u.W_ion_LAr / u.eV                    # 23.6
```

`--only hpp|py|jsonnet|js` (repeatable) writes only some products:

```bash
python generate/generate.py --extra lartpc.units --only py --py myunits.py
```

Things to know:

- **An extended product replaces the stock one; it does not sit beside it.**
  The generated code always uses the C++ namespace `hep::units`, the
  JavaScript global `hepUnits`, and (when installed at the same relative path)
  the Python package `hep_units` and the Jsonnet import `hep/units.libsonnet`.
  A program should see exactly one of them, so give the extended products
  their own install location and put that first on the include, module or
  library path.  Mixing the stock and extended C++ headers in one program
  fails to compile with redefinitions.
- **Do not edit the products by hand.** Each one starts with a "GENERATED ...
  DO NOT EDIT" banner listing its source files.  Regenerate instead.
- **Prefer contributing.**  A unit that is generally useful belongs in
  `units/hep.units`, where every user gets it.  Keep project files for
  project-specific names.
- **Errors name the file and line**:

  ```
  generate.py: error: lartpc.units:7: cannot evaluate 'millivolt': undefined symbol: 'millivolt'
  generate.py: error: mine.units:1: duplicate name 'cm'
  generate.py: error: mine.units:1: 'bad' refers to alias(es) ['V']; only aliases may
  generate.py: error: mine.units:1: cannot evaluate '2**0.5': '**' needs an integer literal exponent
  ```

## Supplying a whole system of units

Positional arguments **replace** the default files.  With them you can build
hep-units products for a different system of units altogether, for example
one based on SI units:

```
# si.units: a small SI-based system.
@section Base units
meter    = 1.
second   = 1.
kilogram = 1.
ampere   = 1.
kelvin   = 1.

@section Derived units
m  = meter
cm = 1.e-2*meter
mm = 1.e-3*meter
s  = second
ns = 1.e-9*second
us = 1.e-6*second
coulomb = ampere*second
joule   = kilogram*meter*meter/(second*second)
volt    = joule/coulomb
eV      = 1.602176634e-19*joule
MeV     = 1.e+6*eV
```

```bash
python generate/generate.py si.units --only py --py si/hep_units/__init__.py
```

```python
import hep_units as u      # the SI build
u.parse("1.6 mm/us")       # 1600.0000000000002 (m/s, to rounding)
```

Code written with the two rules ([multiply to import, divide to
export](philosophy.md)) runs unchanged and gives the same exported numbers in
either system, which is a good way to test that it obeys them.  The
[units-firewall](philosophy.md#the-units-firewall) caution applies: numbers
from programs built with different systems must never meet without an export
and an import.

To combine your own base system with extra files, list them all, in order:

```bash
python generate/generate.py si.units si-extra.units --only py --py ...
# equivalently: python generate/generate.py si.units --extra si-extra.units ...
```

The test suite (`ctest`, `pytest`) checks the values of the default system,
so it is expected to fail on products generated from a different system.

## Generator reference

```
python generate/generate.py [SOURCE.units ...] [--extra FILE ...]
                            [--hpp PATH] [--py PATH] [--jsonnet PATH] [--js PATH]
                            [--only {hpp,py,jsonnet,js} ...]
```

| Option        | Default                          | Meaning                          |
| ------------- | -------------------------------- | -------------------------------- |
| `SOURCE ...`  | `units/clhep.units units/hep.units units/evaluator.units` | files that define the system, in order |
| `--extra`, `-x` | none                           | files read after the sources     |
| `--hpp`       | `include/hep/units.hpp`          | C++ header                       |
| `--py`        | `src/hep_units/__init__.py`      | Python module                    |
| `--jsonnet`   | `jsonnet/hep/units.libsonnet`    | Jsonnet library                  |
| `--js`        | `js/hep-units.js`                | JavaScript module                |
| `--only`      | all four                         | write only the named products    |

Default paths are relative to the hep-units source tree, wherever the
generator is run from.  The generator needs only the Python standard library.

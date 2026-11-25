# hep-units in Python

The Python product is one module, `hep_units`, that uses only the standard
library.  Every unit and constant is a module-level `float`, and `parse()`
evaluates [unit expressions](parse.md).

## Getting it

```bash
pip install .            # from a hep-units source tree, or
uv add <path-or-url>     # in a uv project
```

A CMake install puts the module in `<prefix>/python/hep_units/`; add
`<prefix>/python` to `PYTHONPATH`.  The module is a single file,
`src/hep_units/__init__.py`, and may also be vendored.

```python
import hep_units as u
```

Prefer `import hep_units as u` to `from hep_units import *`.  The module
defines short names such as `m`, `s`, `g`, `L` and `e_SI`, which a star import
would spread over your namespace (aliases such as `V` and `A` are left out of
`__all__`, but `m` and `s` are not).  `u.cm` reads well and cannot be shadowed
by a loop variable named `m`.

## Names

```python
u.mm  u.cm  u.m  u.km          # length; u.mm == 1.0
u.ns  u.us  u.ms  u.s          # time;   u.ns == 1.0
u.eV  u.MeV  u.GeV             # energy; u.MeV == 1.0
u.eplus  u.coulomb             # charge; u.eplus == 1.0
u.volt  u.kilovolt  u.tesla    # derived units
u.rad  u.deg                   # angles
u.pi  u.c_light  u.hbarc  u.k_Boltzmann  u.electron_mass_c2  ...
u.V  u.kV  u.atm  u.micron     # aliases (Geant4 evaluator names)
```

## Import: multiply

```python
length = 10*u.cm             # 100.0  (mm)
speed  = 1.6*u.mm/u.us       # 0.0016 (mm/ns)
field  = 500*u.volt/u.cm     # 5e-05

time = length / speed        # 62500.0 (ns)
```

NumPy arrays obey the same rules, since a unit is just a `float`:

```python
import numpy as np
x_cm = np.array([1.0, 2.5, 4.0])     # e.g. a column read from a file, in cm
x = x_cm * u.cm                      # import
```

## Export: divide

```python
print(f"drift time {time/u.us} us")             # drift time 62.5 us
print(f"field {field/(u.kilovolt/u.cm)} kV/cm") # field 0.5 kV/cm
```

When writing data, put the unit in the name or metadata of what you write:

```python
import csv
with open("drift.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["length_cm", "time_us"])         # the unit travels with the data
    w.writerow([length/u.cm, time/u.us])
```

## Import from text: `parse()`

```python
u.parse(text, symbols=None) -> float
```

```python
u.parse("1.6 mm/us")          # 0.0016
u.parse("500 V/cm")           # 5e-05
u.parse("9.8 m/s^2")          # 9.8e-15
u.parse("2 cm + 3 mm")        # 23.0
```

**Caller symbols.**  Any mapping of names to numbers, looked up before the
table:

```python
consts = {"kTPCWidth": 10*u.cm}
u.parse("kTPCWidth/2 + 1*mm", consts) / u.mm    # 51.0
u.parse("2*V", {"V": 7})                        # 14.0: shadows the alias V
```

**Export to a unit chosen at run time.**

```python
for unit in ("mm/us", "cm/us", "m/s"):
    print(speed / u.parse(unit), unit)
# 1.6 mm/us
# 0.16 cm/us
# 1600.0000000000002 m/s
```

The last line shows ordinary floating-point rounding: `m/s` is not exactly
representable in a system whose base units are mm and ns.  Format the number
(`f"{x:.6g}"`) when printing for people.

**Round trip through text.**

```python
text = f"{length/u.cm} cm"          # '10.0 cm'
assert u.parse(text) == length
```

**Errors** raise `ValueError` with a message that names the problem and the
column.  Arithmetic faults such as `1/0` raise Python's own exceptions (see
[the language](parse.md#errors)).

```python
try:
    u.parse("3 furlong")
except ValueError as err:
    print(err)    # hep_units.parse: unknown unit 'furlong' at column 9 of '3 furlong'
```

## The table

```python
u.TABLE              # dict {name: value} of every unit, constant and alias
len(u.TABLE)         # 229 with the default files
sorted(n for n, v in u.TABLE.items() if v == u.cm)   # ['centimeter', 'cm']
```

## Configuration with units

A typical use is reading a configuration file where people write values with
units.  The reader is the [units firewall](philosophy.md#the-units-firewall):

```python
import json
import hep_units as u

cfg = json.loads('{"length": "2 m", "speed": "0.16 cm/us"}')
length = u.parse(cfg["length"])     # import
speed = u.parse(cfg["speed"])
print(f"{length/speed/u.us} us")    # export: 1250.0 us
```

With [argparse](https://docs.python.org/3/library/argparse.html), `parse` can
be the `type` of an option, so `--pitch "5 mm"` arrives already imported:

```python
ap.add_argument("--pitch", type=u.parse, default=u.parse("4.79 mm"))
```

# The hep-units philosophy

hep-units gives one **system of units** to programs written in C++, Python,
Jsonnet and JavaScript.  It is the system of units of CLHEP (and so of
Geant4), plus a few extra units, some constants of nature and the unit names
that Geant4's GDML reader understands.  This page explains how to think about
it.  The other pages show how to use it in each language.

## A quantity is a plain number in a system of units

hep-units does not attach units to numbers.  There is no "quantity" type and no
dimensional analysis.  A length is a `double`, a time is a `double`, an energy
is a `double`.  What makes the numbers mean something is a convention: every
number inside the program is expressed in **one system of units**, chosen once.

In the CLHEP system the base units are:

| Dimension         | Base unit        | So that ...           |
| ----------------- | ---------------- | --------------------- |
| length            | millimeter       | `mm == 1`             |
| time              | nanosecond       | `ns == 1`             |
| energy            | mega electronvolt| `MeV == 1`            |
| electric charge   | positron charge  | `eplus == 1`          |
| temperature       | kelvin           | `kelvin == 1`         |
| amount of substance | mole           | `mole == 1`           |
| luminous intensity| candela          | `candela == 1`        |
| plane angle       | radian           | `radian == 1`         |

Every other unit is a number derived from these: `cm` is `10`, `m` is `1000`,
`us` is `1000`, `GeV` is `1000`, `volt` is `1e-6` (MeV per eplus), `tesla` is
`0.001`, and so on.  A constant of nature is just a number too, for example
`c_light` is `299.792458` (mm/ns).

The benefit is that arithmetic is ordinary arithmetic.  A speed divided into a
length gives a time, already in the system's time unit, with no conversion
anywhere:

```python
drift_time = 10*cm / (1.6*mm/us)      # 62500.0, in ns because ns == 1
```

The price is that **a number alone does not say what unit it is in**.  `15.0`
might be 15 mm or 1.5 cm written the right way, or 15 cm written the wrong
way.  hep-units keeps the meaning by holding to two rules at the places where
numbers come in and go out.

## Rule 1: multiply to import

> A literal number becomes a quantity by **multiplying it by its unit**.

```cpp
double length = 1.5*cm;          // 15.0 in the system (mm)
double speed  = 1.6*mm/us;       // 0.0016 in the system (mm/ns)
double field  = 500*volt/cm;     // 5e-05 in the system (MeV/eplus/mm)
```

The multiplication **imports** the number into the system of units.  It is
right whatever the system is: if the base length were the meter, `cm` would be
`0.01` and the same line would still give the right value.  So the code never
depends on which unit happens to be `1`.

Corollaries:

- Never write a bare literal for a dimensional quantity (`double length =
  15;`).  Even when the unit is the base unit, write `15*mm`.  The unit then
  says what the number means and the code survives a change of base units.
- A number read from outside the program (a file, a command line, a database,
  a user) is a literal too.  Import it by multiplying by the unit the outside
  world used.  When the outside world writes the unit as text, `parse()`
  does the import for you: `parse("1.5 cm")` is `1.5*cm`.

## Rule 2: divide to export

> A quantity leaves the system by **dividing it by the unit you want it in**.

```python
print(length / cm, "cm")         # 1.5 cm
print(length / mm, "mm")         # 15.0 mm
print(speed / (mm/us), "mm/us")  # 1.6 mm/us
```

The division **exports** the number from the system into the unit you name.
Do it whenever a number goes where the system's convention does not hold:
printing, plotting, writing to a file, passing to a library with another
convention.  The exported number is only meaningful together with the unit
you divided by, so write that unit next to it (in the text, in a column
name, in metadata).

The two rules are inverses: `(x*cm)/cm == x`.  Between import and export, a
program never needs to know which unit is `1`.

## The units firewall

A **system of units** is a convention shared by everything on one side of a
boundary.  Code that obeys the two rules forms a region in which all numbers
mean the same thing.  Where that region meets another one (another program,
a file format, a library or a framework that uses a different system) the
numbers must be translated.  hep-units calls that meeting place a **units
firewall**:

```
     system A (e.g. CLHEP: mm, ns, MeV)  |  system B (e.g. cm, us, GeV)
                                         |
   x_A = ...                             |
   x_B = (x_A / cm)          ---export-->|---import-->  x_B is in cm-based units
                                         |
   y_A = y_B_number * GeV   <--import----|<--export---  y_B_number
```

The firewall is **explicit and in one place**: one function, one module or
one file reader/writer that divides by the units of one side and multiplies by
the units of the other.  Everything else on each side is free of conversions.
The rules are:

1. Pick the firewall's location deliberately.  Typical places are file I/O,
   configuration loading, and the adapter between your code and a library or
   framework with another convention.
2. At the firewall, and only there, export with Rule 2 and import with Rule 1.
   Never let a raw number from one side reach code on the other.
3. When the boundary is text (a configuration file, a GDML attribute, a
   command-line option, a column of a CSV file), **carry the unit in the
   text**: write `"1.5 cm"` rather than `1.5`, and read it back with
   `parse()`.  The text then documents itself and survives a change of system
   on either side.
4. When both sides share the system, the boundary is not a firewall and the
   numbers may cross unchanged.  This is the point of hep-units providing the
   *same* system, bit for bit, in four languages: a Jsonnet configuration that
   says `drift_speed: 1.6*u.mm/u.us` produces JSON that a C++ program using
   `hep::units` reads with no conversion at all.  If the JSON is read by a
   program with another system, the reader is the firewall.

A common example: a framework whose convention is centimeters and GeV hands a
position to code written with hep-units.  The adapter between them is the
firewall:

```cpp
// Firewall: framework (cm, GeV)  ->  hep-units (CLHEP system)
double x = framework_x * cm;          // import: the framework's number is in cm
double e = framework_energy * GeV;    // import: the framework's number is in GeV

// ... code in the CLHEP system, no conversions ...

// Firewall: hep-units  ->  framework
framework_set_x(x / cm);              // export to the framework's convention
```

`parse()` is the general import for text.  A text boundary can carry numbers
in any units the text cares to name, and `parse()` translates each into the
system.  Export to text is the reverse: divide by a unit and write that unit's
name next to the number.

## What hep-units is not

- It does not check dimensions.  `1*cm + 1*ns` is accepted and is
  meaningless.  The two rules and named variables are the defense.
- It does not track which unit a number is in.  That is your convention.
- It is not a units-conversion service between arbitrary systems.  It is
  one system, with the means (multiplication, division and `parse()`) to
  cross into and out of it.

## Where to go next

- [`parse()` language](parse.md): the expressions `parse()` accepts.
- Language guides: [C++](cpp.md), [Python](python.md),
  [Jsonnet](jsonnet.md), [JavaScript](javascript.md).
- [System-of-units files](units-files.md): the `.units` text files that
  define the system, and how to extend them.

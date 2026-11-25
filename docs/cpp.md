# hep-units in C++

The C++ product is one header-only C++17 file, `include/hep/units.hpp`.  Every
unit and constant is an `inline constexpr double` in the namespace
`hep::units`, and `parse()` evaluates [unit expressions](parse.md) at run
time.

## Getting it

With CMake, after installing hep-units (see the top-level `README.md`):

```cmake
find_package(hep_units REQUIRED)
target_link_libraries(myapp PRIVATE hep_units::hep_units)
```

Without CMake, add the `include/` directory to the include path
(`-I<prefix>/include`).  There is nothing to link.

```cpp
#include "hep/units.hpp"
```

## Names

```cpp
using namespace hep::units;     // or: namespace u = hep::units;

mm  cm  m  km  um  nm           // length; mm == 1
ns  us  ms  s                   // time;   ns == 1
eV  keV MeV GeV TeV             // energy; MeV == 1
eplus  coulomb                  // charge; eplus == 1
volt  kilovolt  tesla  gauss    // derived units
rad  deg  sr                    // angles; rad == 1
pi  twopi  c_light  hbarc  k_Boltzmann  electron_mass_c2  ...
```

Each name is a compile-time constant, so it can be used in other `constexpr`
expressions and in `static_assert`:

```cpp
static_assert(cm == 10*mm);
constexpr double pitch = 4.79*mm;
```

The header keeps the structure of each definition, with the value in a
comment, so it doubles as a reference:

```cpp
inline constexpr double centimeter = 10. * millimeter;  // = 10.0
inline constexpr double cm = centimeter;  // = 10.0
inline constexpr double volt = 1.e-6 * megavolt;  // = 1e-06
```

**Aliases.**  The names Geant4's GDML evaluator knows but CLHEP's
`SystemOfUnits.h` lacks (`V`, `kV`, `A`, `T`, `atm`, `micron`, `litre`, ...)
are in the nested namespace `hep::units::aliases`.  This keeps
`using namespace hep::units` from bringing single-letter names such as `A`,
`T` or `V` into your code.  Use them qualified (`aliases::kV`) or through
`parse()`, which always knows them.

## Import: multiply

```cpp
using namespace hep::units;

const double length = 10*cm;          // 100.0  (mm)
const double speed  = 1.6*mm/us;      // 0.0016 (mm/ns)
const double field  = 500*volt/cm;    // 5e-05

const double time = length / speed;   // 62500.0 (ns): no conversion needed
```

A number arriving from outside the program is imported the same way, by the
unit the outside used:

```cpp
const double x = framework_x_in_cm * cm;
```

## Export: divide

```cpp
std::cout << "drift time " << time/us << " us\n";            // drift time 62.5 us
std::cout << "field " << field/(kilovolt/cm) << " kV/cm\n";  // field 0.5 kV/cm
```

Divide by the unit, then write the unit next to the number: on the screen,
in a column name, in a file's metadata.  A number that leaves the program
without a unit is a bug waiting for a reader.

## Import from text: `parse()`

```cpp
double parse(std::string_view text);
double parse(std::string_view text,
             const std::unordered_map<std::string, double>& symbols);

template <class Lookup>
double parse_with(std::string_view text, Lookup&& extra);
```

```cpp
const double s = parse("1.6 mm/us");     // 0.0016
const double e = parse("500 V/cm");      // 5e-05 (V is an alias)
const double g = parse("9.8 m/s^2");     // 9.8e-15
```

**Caller symbols.**  The second argument adds names, looked up before the
table.  This is how a GDML reader evaluates attributes that use the file's
`<constant>`s:

```cpp
const std::unordered_map<std::string, double> consts{{"kTPCWidth", 10*cm}};
parse("kTPCWidth/2 + 1*mm", consts) / mm;     // 51
```

**Any lookup.**  `parse_with()` takes a callable that maps a
`std::string_view` name to a `const double*`, returning `nullptr` for names it
does not know.  Use it to look names up in your own containers without
copying them into an `unordered_map`:

```cpp
const double half = 0.5;
auto find = [&](std::string_view name) -> const double* {
  return name == "half" ? &half : nullptr;
};
parse_with("half*m", find) / cm;              // 50
```

**Export to a unit chosen at run time.**  `parse()` of a unit expression is
that unit's value, so dividing by it exports:

```cpp
const std::string unit = "cm/us";             // e.g. from a command line
std::cout << speed/parse(unit) << " " << unit << "\n";   // 0.16 cm/us
```

**Errors** throw `std::invalid_argument`:

```cpp
try { parse("3 furlong"); }
catch (const std::invalid_argument& err) {
  // hep::units::parse: unknown unit 'furlong' at column 9 of "3 furlong"
}
```

## The table

```cpp
const std::unordered_map<std::string, double>& table();   // every symbol
const double* lookup(std::string_view name);              // nullptr if unknown
```

`table()` holds every unit, constant and alias by name (229 entries with the
default files).  `lookup("mm")` returns a pointer to `1.0`.

## A complete example

```cpp
#include "hep/units.hpp"

#include <iostream>
#include <string>

int main(int argc, char* argv[])
{
  using namespace hep::units;

  // Firewall in: text from the command line, units in the text.
  const double length = parse(argc > 1 ? argv[1] : "10 cm");
  const double speed  = parse(argc > 2 ? argv[2] : "1.6 mm/us");

  // Inside: plain arithmetic in the system of units.
  const double time = length / speed;

  // Firewall out: divide by the unit we print.
  std::cout << time/us << " us\n";
}
```

```console
$ g++ -std=c++17 -I<prefix>/include drift.cpp -o drift
$ ./drift "2 m" "0.16 cm/us"
1250 us
```

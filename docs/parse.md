# The `parse()` language

Every hep-units product has a `parse()` function that evaluates a short
arithmetic expression of numbers, units and constants and returns a number in
the system of units.  It is the [import rule](philosophy.md#rule-1-multiply-to-import)
for text: `parse("1.5 cm")` gives the same value as `1.5*cm`.

The language is the same in C++, Python, Jsonnet and JavaScript, and the four
implementations give **bit-identical** results for arithmetic (see
[Exactness](#exactness)).

## At a glance

| Expression               | Value             | Note                                  |
| ------------------------ | ----------------- | ------------------------------------- |
| `1.5*cm`                 | `15.0`            | explicit multiplication               |
| `1.5 cm`                 | `15.0`            | whitespace multiplies                 |
| `cm`                     | `10.0`            | a unit alone                          |
| `1.6 mm/us`              | `0.0016`          | a speed                               |
| `9.8 m/s^2`              | `9.8e-15`         | `^` binds tighter than `/`            |
| `500 V/cm`               | `5e-05`           | `V` is an alias of `volt`             |
| `2 cm + 3 mm`            | `23.0`            | sums of quantities                    |
| `(1+2)*mm`               | `3.0`             | parentheses                           |
| `-1.5 cm`                | `-15.0`           | a sign                                |
| `s^-1`                   | `1e-09`           | negative power                        |
| `1/s`                    | `1e-09`           | the same                              |
| `2*pi`                   | `6.283185307179586` | constants are names too             |
| `sqrt(2)*cm`             | `14.142135623730951` | functions                          |
| `0.5*0.02`               | `0.01`            | plain arithmetic, no units needed     |
| `0.5*kWireDiam`          | `0.0075`          | with caller symbol `kWireDiam = 0.015` |

## Grammar

From lowest to highest precedence:

```
expr    := term { ('+' | '-') term }
term    := unary { ('*' | '/' | <whitespace>) unary }
unary   := ('+' | '-') unary | power
power   := primary [ ('^' | '**') unary ]          (right-associative)
primary := number | name | name '(' expr {',' expr} ')' | '(' expr ')'
```

### Numbers

C-style decimal floating point: `1`, `1.5`, `1.`, `.5`, `1e-3`, `1.5E+2`,
`1.e3`.  Leading zeros are decimal (`007` is 7).  There are no hexadecimal,
octal, binary or digit-separator forms.  A number has no sign of its own: in
`-1.5` the `-` is the unary operator.

### Names

A name is a letter or `_` followed by letters, digits and `_` (ASCII only), as
in C.  A name is either a function call (when followed by `(`) or a symbol.  A
symbol is looked up:

1. first in the **caller's symbols**, if any were given;
2. then in the hep-units **table** of every unit, constant and alias.

An unknown name is an error.  Names are case sensitive (`mm` and `Mm` are
different; `MeV` is a unit, `mev` is not).

The table holds every name defined by the [system-of-units files](units-files.md):
long and short CLHEP names (`millimeter`, `mm`, `microsecond`, `us`,
`megaelectronvolt`, `MeV`), the extra units (`inch`, `week`, `erg`, ...), the
constants (`pi`, `c_light`, `hbarc`, `k_Boltzmann`, `electron_mass_c2`, ...)
and the aliases that Geant4's expression evaluator knows (`V`, `kV`, `A`, `T`,
`atm`, `micron`, `litre`, ...).  Each language page shows how to list them,
and the [JavaScript demo](demo.html) shows the whole table.

### Operators

| Operator         | Meaning                    | Associativity |
| ---------------- | -------------------------- | ------------- |
| `+`  `-` (binary)| add, subtract              | left          |
| `*`  `/`         | multiply, divide           | left          |
| whitespace       | multiply (*implicit*)      | left          |
| `+`  `-` (unary) | sign                       | right         |
| `^`  `**`        | power                      | right         |

Implicit multiplication happens whenever one operand directly follows another,
with or without whitespace between them, provided the second one starts with a
digit, `.`, `(`, a letter or `_`.  So `1.5 cm`, `2(3)`, `(2)(3)` and
`3 mm ns` are all products.  It has the **same precedence as `*` and `/`** and
is evaluated left to right, so

- `9.8 m/s^2` is `((9.8*m)/(s^2))`,
- `1/s s` is `(1/s)*s`, which is `1`, **not** `1/(s*s)`.
  Write `1/(s*s)` or `s^-2` when that is what you mean.

`^` (or `**`) binds tighter than everything else, including a leading sign,
and is right-associative:

- `-2^2` is `-(2^2)` = `-4`,
- `2^3^2` is `2^(3^2)` = `512`,
- `s^-1` is allowed: the exponent is itself a `unary`.

### Functions

| Function            | Arguments | Meaning                         |
| ------------------- | --------- | ------------------------------- |
| `sqrt(x)`           | 1         | square root                     |
| `sin(x)` `cos(x)` `tan(x)` | 1  | trigonometry, `x` in radians    |
| `asin(x)` `acos(x)` `atan(x)` | 1 | inverse trigonometry, radians |
| `exp(x)` `log(x)`   | 1         | exponential, natural logarithm  |
| `abs(x)`            | 1         | absolute value                  |
| `pow(x, y)`         | 2         | `x^y`                           |
| `min(x, y)` `max(x, y)` | 2     | smaller, larger                 |

Since `radian == 1` and `degree == pi/180`, `sin(30 deg)` is `0.5` (to
rounding).  Arguments are full expressions: `max(1 cm, 5 mm)` is `10.0`.
Function names are not looked up in the symbol table, and symbols cannot be
called.

### Whitespace

Spaces, tabs and newlines may appear between any two tokens.  Between two
operands they mean multiplication; anywhere else they are ignored.

## Caller symbols

Every `parse()` takes an optional second argument: a mapping of extra names to
numbers.  These are looked up **before** the table, so they may add names
(`kWireDiam`) or shadow units (`m`, `V`).  This is how a GDML reader evaluates
attributes that refer to the file's own `<constant>`s:

```
parse("kTPCWidth/2 + 1", {kTPCWidth: 10})   ->  6.0
parse("EWProfileLength*cm", {EWProfileLength: 2.5})  ->  25.0
parse("2*V", {V: 7})                        ->  14.0     (shadows the alias V)
```

Caller symbols hold numbers that are already in the system of units (or that
are dimensionless), exactly as the table's entries are.

## Errors

`parse()` rejects, with a message that names the problem, the column and the
text:

| Input            | Error                                 |
| ---------------- | ------------------------------------- |
| `""`             | empty expression                      |
| `1 +`            | missing operand                       |
| `(1`             | missing `)`                           |
| `1)`             | unexpected `)`                        |
| `furlong`        | unknown unit `furlong`                |
| `foo(1)`         | unknown function `foo`                |
| `sqrt(1, 2)`     | `sqrt()` takes 1 argument(s)          |
| `1 $ 2`          | unexpected `$`                        |
| `.`              | bad number                            |

The column is a hint for people: the languages may point at different places
in the same text (Jsonnet points at the start of the offending token, the
others just after it).  How an error is reported depends on the language: C++ throws
`std::invalid_argument`, Python raises `ValueError`, Jsonnet raises an
evaluation error and JavaScript throws `Error`.  Every message starts with
`hep::units::parse:` (C++) or `hep_units.parse:` (the others).

Arithmetic faults are left to the language and so differ between them:

| Input       | C++     | JavaScript  | Python                          | Jsonnet                |
| ----------- | ------- | ----------- | ------------------------------- | ---------------------- |
| `1/0`       | `inf`   | `Infinity`  | raises `ZeroDivisionError`      | error "Division by zero" |
| `sqrt(-1)`  | `nan`   | `NaN`       | raises `ValueError` (math domain error) | error "Not a number" |
| `log(0)`    | `-inf`  | `-Infinity` | raises `ValueError` (math domain error) | error "Overflow"  |

In Python, catch `ArithmeticError` as well as `ValueError` if the text may
hold such expressions.

## Exactness

For expressions made of numbers, names and the operators `+ - * / ^`, all four
implementations return the same `double`, bit for bit.  The test
`test/test_parity.py` checks this for every case of `test/parse-cases.txt`,
which is a good collection of further examples.  The functions call each
language's math library and may differ in the last bit (this has been seen for
`acos(0.3)` in go-jsonnet).

## Patterns

**Units in configuration text.**  Store `"drift_speed": "1.6 mm/us"` and import
it with `parse()`.  The file is readable, and correct whatever the reader's
base units.

**Exporting to text that `parse()` reads back.**  Divide by a unit and write
its name:

```python
text = f"{length/cm} cm"        # "1.5 cm"
assert parse(text) == length    # round trip (exact here; in general up to rounding)
```

**A unit as a string.**  `parse("mm/us")` is the value of the unit `mm/us`, so
`x / parse(unit)` exports `x` to a unit chosen at run time:

```python
for unit in ("mm/us", "cm/us", "m/s"):
    print(speed / parse(unit), unit)
```

**Plain arithmetic.**  Without any names, `parse()` is a calculator.  GDML
attributes such as `"0.5*0.02"` or `"2.3/2"` are evaluated this way.

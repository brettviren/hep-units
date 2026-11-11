#!/usr/bin/env python3
# Copyright (c) 2026, Brookhaven Science Associates, LLC
# SPDX-License-Identifier: Apache-2.0
"""
Generate the hep-units products (C++ header, Python module, Jsonnet library)
from the source-of-truth ``.units`` files.

This is a DEVELOPER tool.  Its outputs are committed into the package so that
downstream builds never need to run it (and never need this script's runtime,
which is nothing more than the Python standard library).  Re-run it whenever a
``.units`` source changes:

    python generate/generate.py

By default it reads ``units/clhep.units`` then ``units/hep.units`` and writes:

    include/hep/units.hpp
    src/hep_units/__init__.py
    jsonnet/hep/units.libsonnet

The source-of-truth format
--------------------------
A ``.units`` file is a sequence of lines.  Blank lines and lines whose first
non-space character is ``#`` are ignored.  Otherwise a line is one of:

    @section <free text>      -- a grouping label for the definitions that
                                 follow (used only to organise the output)
    @kind unit|constant       -- tag the following definitions as either a
                                 "unit" or a "constant" (default: unit)
    NAME = EXPRESSION         -- define symbol NAME.

NAME is a C/Python identifier.  EXPRESSION is simple arithmetic over numeric
literals and previously-defined NAMEs using ``+ - * / **`` and parentheses
(unary +/- allowed).  Definitions are evaluated in order; a name must be
defined before it is used.  Files given on the command line are concatenated in
order, so later files may reference names from earlier ones.

All defined symbols -- units and constants alike -- become named values in each
product and populate the lookup table used by the generated ``parse()``
function.
"""

import ast
import argparse
import operator
import re
from pathlib import Path

# --------------------------------------------------------------------------
# Parsing the source-of-truth format.
# --------------------------------------------------------------------------

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval(node, symbols):
    """Safely evaluate a parsed arithmetic expression against ``symbols``."""
    if isinstance(node, ast.Expression):
        return _eval(node.body, symbols)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"non-numeric constant: {node.value!r}")
    if isinstance(node, ast.Name):
        if node.id not in symbols:
            raise ValueError(f"undefined symbol: {node.id!r}")
        return symbols[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval(node.left, symbols),
                                      _eval(node.right, symbols))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNOPS:
        return _UNOPS[type(node.op)](_eval(node.operand, symbols))
    raise ValueError(f"unsupported expression element: {ast.dump(node)}")


class Symbol:
    __slots__ = ("name", "expr", "value", "section", "kind", "source")

    def __init__(self, name, expr, value, section, kind, source):
        self.name = name
        self.expr = expr
        self.value = value
        self.section = section
        self.kind = kind
        self.source = source


def parse_sources(paths):
    """Parse the given ``.units`` files, returning an ordered list of Symbol."""
    symbols = {}           # name -> value, for expression evaluation
    records = []           # ordered Symbol list
    section = None
    kind = "unit"
    for path in paths:
        path = Path(path)
        for lineno, raw in enumerate(path.read_text().splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("@section"):
                section = line[len("@section"):].strip() or None
                continue
            if line.startswith("@kind"):
                kind = line[len("@kind"):].strip()
                if kind not in ("unit", "constant"):
                    raise ValueError(
                        f"{path}:{lineno}: @kind must be 'unit' or 'constant', "
                        f"got {kind!r}")
                continue
            if "=" not in line:
                raise ValueError(f"{path}:{lineno}: not a definition: {raw!r}")
            name, expr = line.split("=", 1)
            name = name.strip()
            expr = expr.split("#", 1)[0].strip()   # allow trailing comment
            if not name.isidentifier():
                raise ValueError(f"{path}:{lineno}: invalid name {name!r}")
            if name in symbols:
                raise ValueError(f"{path}:{lineno}: duplicate name {name!r}")
            try:
                value = _eval(ast.parse(expr, mode="eval"), symbols)
            except Exception as err:
                raise ValueError(
                    f"{path}:{lineno}: cannot evaluate {expr!r}: {err}") from err
            symbols[name] = value
            records.append(Symbol(name, expr, value, section, kind, path.name))
    return records


# --------------------------------------------------------------------------
# Rendering an expression back to source, referencing prior symbols by name.
#
# The generated products keep the *structure* of each definition (e.g. C++
# `cm2 = cm*cm`) rather than a flattened numeric literal, so a reader sees how
# the units are built up.  The renderer walks the same AST used for evaluation
# and prints it with minimal parentheses, which -- because C++, Python and
# Jsonnet share operator precedence, left-associativity and IEEE-754 `double`
# semantics -- yields byte-for-byte equivalent arithmetic and therefore
# identical values in all three languages.
# --------------------------------------------------------------------------

_PREC = {ast.Add: 1, ast.Sub: 1, ast.Mult: 2, ast.Div: 2}
_OPSYM = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}
_UNARY_PREC = 3
_POW_PREC = 4  # an expanded power is always parenthesized, so treat as atomic


def _int_exponent(node):
    """Return the integer value of a Pow exponent node, or None if not integral."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, int)):
        return -node.operand.value
    return None


def _jsonnet_number(tok):
    """Normalise a C/Python numeric literal token to valid Jsonnet syntax.

    Jsonnet requires a digit on both sides of the decimal point, so `1.` and
    `1.e-6` (legal in C++/Python) must become `1.0` and `1.0e-6`.
    """
    tok = re.sub(r"^\.", "0.", tok)            # .5     -> 0.5
    tok = re.sub(r"\.(?=[eE]|$)", ".0", tok)   # 1.     -> 1.0 ; 1.e-6 -> 1.0e-6
    return tok


def render_expr(expr, name_fmt, jsonnet=False):
    """Render source expression ``expr`` with names mapped through ``name_fmt``."""
    tree = ast.parse(expr, mode="eval").body

    def literal(node):
        tok = expr[node.col_offset:node.end_col_offset]
        return _jsonnet_number(tok) if jsonnet else tok

    def rec(node, parent_prec, is_right):
        if isinstance(node, ast.Constant):
            return literal(node)
        if isinstance(node, ast.Name):
            return name_fmt(node.id)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            operand = rec(node.operand, _UNARY_PREC, False)
            sign = "-" if isinstance(node.op, ast.USub) else "+"
            s = sign + operand
            return f"({s})" if parent_prec > _UNARY_PREC else s
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            n = _int_exponent(node.right)
            if n is None:
                raise ValueError(
                    f"power in {expr!r}: exponent must be an integer literal "
                    "(C++ constexpr has no runtime pow); expand it manually")
            base = rec(node.left, _POW_PREC, False)
            if n == 0:
                return "1"
            if n >= 1:
                return "(" + " * ".join([base] * n) + ")"
            return "(1.0 / (" + " * ".join([base] * (-n)) + "))"
        if isinstance(node, ast.BinOp) and type(node.op) in _PREC:
            prec = _PREC[type(node.op)]
            left = rec(node.left, prec, False)
            right = rec(node.right, prec, True)
            s = f"{left} {_OPSYM[type(node.op)]} {right}"
            need = prec < parent_prec or (prec == parent_prec and is_right)
            return f"({s})" if need else s
        raise ValueError(f"unsupported expression element in {expr!r}: "
                         f"{ast.dump(node)}")

    return rec(tree, 0, False)


# --------------------------------------------------------------------------
# Emission helpers.
# --------------------------------------------------------------------------

def _num(value):
    """Round-trippable literal for a double; identical text in C++/Py/Jsonnet."""
    return repr(float(value))


def _grouped(records):
    """Yield (section, [Symbol, ...]) preserving order, coalescing runs."""
    cur = None
    bucket = []
    for r in records:
        key = (r.section, r.kind)
        if key != cur and bucket:
            yield cur, bucket
            bucket = []
        cur = key
        bucket.append(r)
    if bucket:
        yield cur, bucket


_COPYRIGHT = "Copyright (c) 2026, Brookhaven Science Associates, LLC"
_SPDX = "SPDX-License-Identifier: Apache-2.0"

_BANNER = (
    "GENERATED by hep-units generate/generate.py -- DO NOT EDIT.\n"
    "Edit the units/*.units sources and re-run the generator instead.\n"
    "Sources: {sources}"
)


def _header_lines(sources, prefix):
    """License/copyright + generated-from banner, each line commented."""
    lines = [_COPYRIGHT, _SPDX, ""]
    lines += _BANNER.format(sources=", ".join(sources)).splitlines()
    return [prefix + line if line else prefix.rstrip() for line in lines]


# --------------------------------------------------------------------------
# C++ header.
# --------------------------------------------------------------------------

_CPP_PARSE = r"""
// ------------------------------------------------------------------------
// Lookup table of every named symbol (units and constants).
// ------------------------------------------------------------------------
inline const std::unordered_map<std::string, double>& table()
{
  static const std::unordered_map<std::string, double> t = {
%(entries)s
  };
  return t;
}

// Resolve a symbol name in table(); nullptr if unknown.
inline const double* lookup(std::string_view name)
{
  const auto it = table().find(std::string(name));
  return it == table().end() ? nullptr : &it->second;
}

// ------------------------------------------------------------------------
// parse() -- evaluate an arithmetic expression of numbers, units and
// constants in the system of units.
//
//     "1.5*cm"   "1.5 cm"   "9.8 m/s^2"   "2*pi"   "0.5*0.02"   "2.3/2"
//     "(1+2)*mm"   "-1.5 cm"   "s^-1"   "sqrt(2)*cm"   "500*V/cm"
//
// Grammar (lowest to highest precedence):
//
//     expr    := term { ('+' | '-') term }
//     term    := unary { ('*' | '/' | <whitespace>) unary }
//     unary   := ('+' | '-') unary | power
//     power   := primary [ ('^' | '**') unary ]          (right-associative)
//     primary := number | name | name '(' expr {',' expr} ')' | '(' expr ')'
//
// Two operands side by side (whitespace) multiply, so "1.5 cm" is 1.5*cm.
// '^' binds tighter than a sign: "-2^2" is -4.  A name is looked up first in
// the caller's symbols (parse_with / parse(text, symbols)), then in table().
// Functions: sqrt sin cos tan asin acos atan exp log pow abs min max.
// Errors throw std::invalid_argument.
// ------------------------------------------------------------------------
namespace detail {

template <class Lookup>
class Parser {
public:
  Parser(std::string_view text, Lookup& extra) : s_(text), extra_(extra) {}

  double run()
  {
    skip();
    if (i_ >= s_.size()) { fail("empty expression"); }
    const double v = expr();
    skip();
    if (i_ < s_.size()) { fail("unexpected '" + std::string(1, s_[i_]) + "'"); }
    return v;
  }

private:
  std::string_view s_;
  Lookup& extra_;
  std::size_t i_ = 0;

  [[noreturn]] void fail(const std::string& what) const
  {
    throw std::invalid_argument("hep::units::parse: " + what + " at column "
                                + std::to_string(i_) + " of \"" + std::string(s_) + "\"");
  }

  void skip()
  {
    while (i_ < s_.size() && std::isspace(static_cast<unsigned char>(s_[i_]))) { ++i_; }
  }

  static bool name_start(char c) { return std::isalpha(static_cast<unsigned char>(c)) || c == '_'; }
  static bool name_char(char c) { return std::isalnum(static_cast<unsigned char>(c)) || c == '_'; }
  static bool digit(char c) { return c >= '0' && c <= '9'; }

  bool at(char c)
  {
    skip();
    return i_ < s_.size() && s_[i_] == c;
  }
  bool at_power()
  {
    skip();
    return i_ < s_.size() && (s_[i_] == '^' || (s_[i_] == '*' && i_ + 1 < s_.size() && s_[i_ + 1] == '*'));
  }
  // Does an operand start here (for implicit multiplication)?
  bool at_operand()
  {
    skip();
    if (i_ >= s_.size()) { return false; }
    const char c = s_[i_];
    return digit(c) || c == '.' || c == '(' || name_start(c);
  }

  double expr()
  {
    double v = term();
    while (true) {
      if (at('+')) { ++i_; v += term(); }
      else if (at('-')) { ++i_; v -= term(); }
      else { return v; }
    }
  }

  double term()
  {
    double v = unary();
    while (true) {
      if (at('*') && !at_power()) { ++i_; v *= unary(); }
      else if (at('/')) { ++i_; v /= unary(); }
      else if (at_operand()) { v *= unary(); }
      else { return v; }
    }
  }

  double unary()
  {
    if (at('+')) { ++i_; return unary(); }
    if (at('-')) { ++i_; return -unary(); }
    return power();
  }

  double power()
  {
    const double b = primary();
    if (at_power()) {
      i_ += (s_[i_] == '^') ? 1 : 2;
      return std::pow(b, unary());
    }
    return b;
  }

  double number()
  {
    const std::size_t b = i_;
    while (i_ < s_.size() && digit(s_[i_])) { ++i_; }
    if (i_ < s_.size() && s_[i_] == '.') {
      ++i_;
      while (i_ < s_.size() && digit(s_[i_])) { ++i_; }
    }
    if (i_ < s_.size() && (s_[i_] == 'e' || s_[i_] == 'E')) {
      std::size_t k = i_ + 1;
      if (k < s_.size() && (s_[k] == '+' || s_[k] == '-')) { ++k; }
      if (k < s_.size() && digit(s_[k])) {
        i_ = k;
        while (i_ < s_.size() && digit(s_[i_])) { ++i_; }
      }
    }
    const std::string text(s_.substr(b, i_ - b));
    if (text == ".") { fail("bad number"); }
    return std::strtod(text.c_str(), nullptr);
  }

  double call(const std::string& f, const std::vector<double>& a)
  {
    const auto need = [&](std::size_t n) {
      if (a.size() != n) { fail(f + "() takes " + std::to_string(n) + " argument(s)"); }
    };
    if (f == "pow") { need(2); return std::pow(a[0], a[1]); }
    if (f == "min") { need(2); return std::fmin(a[0], a[1]); }
    if (f == "max") { need(2); return std::fmax(a[0], a[1]); }
    need(1);
    const double x = a[0];
    if (f == "sqrt") { return std::sqrt(x); }
    if (f == "sin") { return std::sin(x); }
    if (f == "cos") { return std::cos(x); }
    if (f == "tan") { return std::tan(x); }
    if (f == "asin") { return std::asin(x); }
    if (f == "acos") { return std::acos(x); }
    if (f == "atan") { return std::atan(x); }
    if (f == "exp") { return std::exp(x); }
    if (f == "log") { return std::log(x); }
    if (f == "abs") { return std::fabs(x); }
    fail("unknown function '" + f + "'");
  }

  double primary()
  {
    skip();
    if (i_ >= s_.size()) { fail("missing operand"); }
    const char c = s_[i_];
    if (c == '(') {
      ++i_;
      const double v = expr();
      if (!at(')')) { fail("missing ')'"); }
      ++i_;
      return v;
    }
    if (digit(c) || c == '.') { return number(); }
    if (name_start(c)) {
      const std::size_t b = i_;
      while (i_ < s_.size() && name_char(s_[i_])) { ++i_; }
      const std::string name(s_.substr(b, i_ - b));
      if (at('(')) {
        ++i_;
        std::vector<double> args{expr()};
        while (at(',')) { ++i_; args.push_back(expr()); }
        if (!at(')')) { fail("missing ')'"); }
        ++i_;
        return call(name, args);
      }
      if (const double* v = extra_(std::string_view(name))) { return *v; }
      if (const double* v = lookup(name)) { return *v; }
      fail("unknown unit '" + name + "'");
    }
    fail("unexpected '" + std::string(1, c) + "'");
  }
};

}  // namespace detail

// Evaluate `text` with an extra symbol lookup tried before table():
// `extra(std::string_view name)` returns a `const double*`, or nullptr when
// it does not know the name.
template <class Lookup>
double parse_with(std::string_view text, Lookup&& extra)
{
  detail::Parser<std::remove_reference_t<Lookup>> p(text, extra);
  return p.run();
}

// Evaluate `text` with extra named values (e.g. a GDML file's <constant>s),
// which take precedence over table().
inline double parse(std::string_view text,
                    const std::unordered_map<std::string, double>& symbols)
{
  return parse_with(text, [&symbols](std::string_view name) -> const double* {
    const auto it = symbols.find(std::string(name));
    return it == symbols.end() ? nullptr : &it->second;
  });
}

// Evaluate `text` with table() only.
inline double parse(std::string_view text)
{
  return parse_with(text, [](std::string_view) -> const double* { return nullptr; });
}
"""


def emit_cpp(records, sources):
    out = []
    out.extend(_header_lines(sources, "// "))
    out.append("")
    out.append("#pragma once")
    out.append("")
    out.append("#include <cctype>")
    out.append("#include <cmath>")
    out.append("#include <cstdlib>")
    out.append("#include <stdexcept>")
    out.append("#include <string>")
    out.append("#include <string_view>")
    out.append("#include <type_traits>")
    out.append("#include <unordered_map>")
    out.append("#include <vector>")
    out.append("")
    out.append("namespace hep::units {")
    out.append("")
    for (section, kind), syms in _grouped(records):
        label = section or ""
        tag = "" if kind == "unit" else " (constants)"
        out.append(f"// ---- {label}{tag} ----")
        for sym in syms:
            rhs = render_expr(sym.expr, lambda n: n)
            out.append(f"inline constexpr double {sym.name} = {rhs};"
                       f"  // = {_num(sym.value)}")
        out.append("")
    entries = "\n".join(f'    {{"{s.name}", {s.name}}},' for s in records)
    out.append(_CPP_PARSE.strip("\n") % {"entries": entries})
    out.append("")
    out.append("}  // namespace hep::units")
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Python module.
# --------------------------------------------------------------------------

_PY_PARSE = r'''
#: Lookup table of every named symbol (units and constants).
TABLE = {
%(entries)s
}

import math as _math

_FUNCS = {
    "sqrt": (1, _math.sqrt), "sin": (1, _math.sin), "cos": (1, _math.cos),
    "tan": (1, _math.tan), "asin": (1, _math.asin), "acos": (1, _math.acos),
    "atan": (1, _math.atan), "exp": (1, _math.exp), "log": (1, _math.log),
    "abs": (1, abs), "pow": (2, _math.pow), "min": (2, min), "max": (2, max),
}


class _Parser:
    def __init__(self, text, symbols):
        self.s = text
        self.i = 0
        self.symbols = symbols or {}

    def fail(self, what):
        raise ValueError(f"hep_units.parse: {what} at column {self.i} of {self.s!r}")

    def skip(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def at(self, c):
        self.skip()
        return self.s.startswith(c, self.i)

    def at_power(self):
        return self.at("^") or self.at("**")

    def at_operand(self):
        self.skip()
        if self.i >= len(self.s):
            return False
        c = self.s[self.i]
        return c.isdigit() or c == "." or c == "(" or c.isalpha() or c == "_"

    def run(self):
        self.skip()
        if self.i >= len(self.s):
            self.fail("empty expression")
        v = self.expr()
        self.skip()
        if self.i < len(self.s):
            self.fail(f"unexpected {self.s[self.i]!r}")
        return v

    def expr(self):
        v = self.term()
        while True:
            if self.at("+"):
                self.i += 1
                v += self.term()
            elif self.at("-"):
                self.i += 1
                v -= self.term()
            else:
                return v

    def term(self):
        v = self.unary()
        while True:
            if self.at("*") and not self.at("**"):
                self.i += 1
                v *= self.unary()
            elif self.at("/"):
                self.i += 1
                v /= self.unary()
            elif self.at_operand():
                v *= self.unary()
            else:
                return v

    def unary(self):
        if self.at("+"):
            self.i += 1
            return self.unary()
        if self.at("-"):
            self.i += 1
            return -self.unary()
        return self.power()

    def power(self):
        b = self.primary()
        if self.at_power():
            self.i += 1 if self.s[self.i] == "^" else 2
            return b ** self.unary()
        return b

    def number(self):
        s, b = self.s, self.i
        n = len(s)
        while self.i < n and s[self.i].isdigit():
            self.i += 1
        if self.i < n and s[self.i] == ".":
            self.i += 1
            while self.i < n and s[self.i].isdigit():
                self.i += 1
        if self.i < n and s[self.i] in "eE":
            k = self.i + 1
            if k < n and s[k] in "+-":
                k += 1
            if k < n and s[k].isdigit():
                self.i = k
                while self.i < n and s[self.i].isdigit():
                    self.i += 1
        text = s[b:self.i]
        if text == ".":
            self.fail("bad number")
        return float(text)

    def primary(self):
        self.skip()
        if self.i >= len(self.s):
            self.fail("missing operand")
        c = self.s[self.i]
        if c == "(":
            self.i += 1
            v = self.expr()
            if not self.at(")"):
                self.fail("missing ')'")
            self.i += 1
            return v
        if c.isdigit() or c == ".":
            return self.number()
        if c.isalpha() or c == "_":
            b = self.i
            while self.i < len(self.s) and (self.s[self.i].isalnum() or self.s[self.i] == "_"):
                self.i += 1
            name = self.s[b:self.i]
            if self.at("("):
                self.i += 1
                args = [self.expr()]
                while self.at(","):
                    self.i += 1
                    args.append(self.expr())
                if not self.at(")"):
                    self.fail("missing ')'")
                self.i += 1
                if name not in _FUNCS:
                    self.fail(f"unknown function {name!r}")
                nargs, fn = _FUNCS[name]
                if len(args) != nargs:
                    self.fail(f"{name}() takes {nargs} argument(s)")
                return float(fn(*args))
            if name in self.symbols:
                return self.symbols[name]
            if name in TABLE:
                return TABLE[name]
            self.fail(f"unknown unit {name!r}")
        self.fail(f"unexpected {c!r}")


def parse(text, symbols=None):
    """Evaluate an arithmetic expression of numbers, units and constants.

    ::

        parse("1.5*cm")   parse("1.5 cm")   parse("9.8 m/s^2")   parse("2*pi")
        parse("0.5*0.02") parse("(1+2)*mm") parse("s^-1")  parse("sqrt(2)*cm")

    Grammar (lowest to highest precedence)::

        expr    := term { ('+' | '-') term }
        term    := unary { ('*' | '/' | <whitespace>) unary }
        unary   := ('+' | '-') unary | power
        power   := primary [ ('^' | '**') unary ]          (right-associative)
        primary := number | name | name '(' expr {',' expr} ')' | '(' expr ')'

    Two operands side by side multiply ("1.5 cm" is 1.5*cm); '^' binds
    tighter than a sign ("-2^2" is -4).  Names are looked up first in
    ``symbols`` (a mapping, e.g. a GDML file's constants), then in
    :data:`TABLE`.  Functions: sqrt sin cos tan asin acos atan exp log pow
    abs min max.  Errors raise ValueError.
    """
    return _Parser(text, symbols).run()
'''


def emit_python(records, sources):
    out = []
    out.extend(_header_lines(sources, "# "))
    out.append('"""hep-units: the CLHEP HEP system of units, plus local additions."""')
    out.append("")
    names = [s.name for s in records]
    out.append("__all__ = [")
    for name in names:
        out.append(f'    "{name}",')
    out.append('    "TABLE",')
    out.append('    "parse",')
    out.append("]")
    out.append("")
    for (section, kind), syms in _grouped(records):
        label = section or ""
        tag = "" if kind == "unit" else " (constants)"
        out.append(f"# ---- {label}{tag} ----")
        for sym in syms:
            rhs = render_expr(sym.expr, lambda n: n)
            out.append(f"{sym.name} = {rhs}  # = {_num(sym.value)}")
        out.append("")
    entries = "\n".join(f'    "{s.name}": {s.name},' for s in records)
    out.append(_PY_PARSE.strip("\n") % {"entries": entries})
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Jsonnet library.
# --------------------------------------------------------------------------

_JSONNET_PARSE = r"""
  // Resolve one atom: a numeric literal or a known symbol name (kept for
  // compatibility; parse() does its own lexing).
  resolve(atom)::
    local c = std.substr(atom, 0, 1);
    if c == '.' || c == '-' || c == '+'
       || (std.codepoint(c) >= 48 && std.codepoint(c) <= 57)
    then std.parseJson(atom)
    else if std.objectHas($.table, atom) then $.table[atom]
    else error 'hep_units.parse: unknown unit ' + atom,

  // parse(text, symbols={}) -- evaluate an arithmetic expression of numbers,
  // units and constants in the system of units.
  //
  //   u.parse('1.5*cm')  u.parse('1.5 cm')  u.parse('9.8 m/s^2')  u.parse('2*pi')
  //   u.parse('0.5*0.02')  u.parse('(1+2)*mm')  u.parse('s^-1')  u.parse('sqrt(2)*cm')
  //
  // Grammar (lowest to highest precedence):
  //   expr    := term { ('+' | '-') term }
  //   term    := unary { ('*' | '/' | <whitespace>) unary }
  //   unary   := ('+' | '-') unary | power
  //   power   := primary [ ('^' | '**') unary ]          (right-associative)
  //   primary := number | name | name '(' expr {',' expr} ')' | '(' expr ')'
  //
  // Two operands side by side multiply ('1.5 cm' is 1.5*cm); '^' binds tighter
  // than a sign ('-2^2' is -4).  Names are looked up first in `symbols` (an
  // object, e.g. a GDML file's constants), then in table.  Functions: sqrt sin
  // cos tan asin acos atan exp log pow abs min max.
  parse(text, symbols={})::
    local root = $;
    local n = std.length(text);
    local fail(what, i) = error 'hep_units.parse: %s at column %d of "%s"' % [what, i, text];
    local cp(i) = if i < n then std.codepoint(text[i]) else -1;
    local isdigit(i) = cp(i) >= 48 && cp(i) <= 57;
    local isalpha(i) = (cp(i) >= 65 && cp(i) <= 90) || (cp(i) >= 97 && cp(i) <= 122) || cp(i) == 95;
    local isspace(i) = i < n && std.member(' \t\n\r', text[i]);
    local scan(i, pred) = if pred(i) then scan(i + 1, pred) else i;
    // A number's end; returns the index after the last character.
    local number_end(i) =
      local a = scan(i, isdigit);
      local b = if a < n && text[a] == '.' then scan(a + 1, isdigit) else a;
      if b < n && (text[b] == 'e' || text[b] == 'E') then
        local k = if b + 1 < n && (text[b + 1] == '+' || text[b + 1] == '-') then b + 2 else b + 1;
        if isdigit(k) then scan(k, isdigit) else b
      else b;
    // C-style number text -> valid JSON number ('1.' '.5' '1.e3' '007').
    local json_number(t, i) =
      local me = std.split(std.strReplace(t, 'E', 'e'), 'e');
      local mf = std.split(me[0], '.');
      local ip = std.lstripChars(mf[0], '0');
      local fp = if std.length(mf) > 1 then mf[1] else '';
      if mf[0] == '' && fp == '' then fail('bad number', i)
      else std.parseJson((if ip == '' then '0' else ip) + '.' + (if fp == '' then '0' else fp)
                         + (if std.length(me) > 1 then 'e' + me[1] else ''));
    // Tokens: {k: 'num'|'name'|'op', v, at}.  '**' becomes '^'.
    local lex(i, acc) =
      if i >= n then acc
      else if isspace(i) then lex(i + 1, acc)
      else if isdigit(i) || text[i] == '.' then
        local j = number_end(i);
        lex(j, acc + [{ k: 'num', v: json_number(text[i:j], i), at: i }])
      else if isalpha(i) then
        local j = scan(i, function(x) isalpha(x) || isdigit(x));
        lex(j, acc + [{ k: 'name', v: text[i:j], at: i }])
      else if text[i] == '*' && i + 1 < n && text[i + 1] == '*' then
        lex(i + 2, acc + [{ k: 'op', v: '^', at: i }])
      else if std.member('+-*/^(),', text[i]) then
        lex(i + 1, acc + [{ k: 'op', v: text[i], at: i }])
      else fail("unexpected '%s'" % text[i], i);
    local toks = lex(0, []);
    local nt = std.length(toks);
    local is(p, v) = p < nt && toks[p].k == 'op' && toks[p].v == v;
    local col(p) = if p < nt then toks[p].at else n;
    local operand(p) = p < nt && (toks[p].k != 'op' || toks[p].v == '(');
    local funcs = {
      sqrt: [1, function(a) std.sqrt(a[0])], sin: [1, function(a) std.sin(a[0])],
      cos: [1, function(a) std.cos(a[0])], tan: [1, function(a) std.tan(a[0])],
      asin: [1, function(a) std.asin(a[0])], acos: [1, function(a) std.acos(a[0])],
      atan: [1, function(a) std.atan(a[0])], exp: [1, function(a) std.exp(a[0])],
      log: [1, function(a) std.log(a[0])], abs: [1, function(a) std.abs(a[0])],
      pow: [2, function(a) std.pow(a[0], a[1])], min: [2, function(a) std.min(a[0], a[1])],
      max: [2, function(a) std.max(a[0], a[1])],
    };
    // Each rule takes a token position and returns { v, p } (value, next position).
    local expr(p) =
      local loop(r) =
        if is(r.p, '+') then local t = term(r.p + 1); loop({ v: r.v + t.v, p: t.p })
        else if is(r.p, '-') then local t = term(r.p + 1); loop({ v: r.v - t.v, p: t.p })
        else r;
      loop(term(p)),
    term(p) =
      local loop(r) =
        if is(r.p, '*') then local u = unary(r.p + 1); loop({ v: r.v * u.v, p: u.p })
        else if is(r.p, '/') then local u = unary(r.p + 1); loop({ v: r.v / u.v, p: u.p })
        else if operand(r.p) then local u = unary(r.p); loop({ v: r.v * u.v, p: u.p })
        else r;
      loop(unary(p)),
    unary(p) =
      if is(p, '+') then unary(p + 1)
      else if is(p, '-') then local u = unary(p + 1); { v: -u.v, p: u.p }
      else power(p),
    power(p) =
      local b = primary(p);
      if is(b.p, '^') then local e = unary(b.p + 1); { v: std.pow(b.v, e.v), p: e.p }
      else b,
    args(p, acc) =
      local a = expr(p);
      if is(a.p, ',') then args(a.p + 1, acc + [a.v]) else { v: acc + [a.v], p: a.p },
    primary(p) =
      if p >= nt then fail('missing operand', n)
      else if is(p, '(') then
        local e = expr(p + 1);
        if is(e.p, ')') then { v: e.v, p: e.p + 1 } else fail("missing ')'", col(e.p))
      else if toks[p].k == 'num' then { v: toks[p].v, p: p + 1 }
      else if toks[p].k == 'name' then
        local name = toks[p].v;
        if is(p + 1, '(') then
          local a = args(p + 2, []);
          if !is(a.p, ')') then fail("missing ')'", col(a.p))
          else if !std.objectHas(funcs, name) then fail("unknown function '%s'" % name, toks[p].at)
          else if std.length(a.v) != funcs[name][0] then
            fail('%s() takes %d argument(s)' % [name, funcs[name][0]], toks[p].at)
          else { v: funcs[name][1](a.v), p: a.p + 1 }
        else if std.objectHas(symbols, name) then { v: symbols[name], p: p + 1 }
        else if std.objectHas(root.table, name) then { v: root.table[name], p: p + 1 }
        else fail("unknown unit '%s'" % name, toks[p].at)
      else fail("unexpected '%s'" % toks[p].v, toks[p].at);
    if nt == 0 then fail('empty expression', 0)
    else
      local r = expr(0);
      if r.p < nt then fail("unexpected '%s'" % toks[r.p].v, toks[r.p].at) else r.v,
"""


def emit_jsonnet(records, sources):
    out = []
    out.extend(_header_lines(sources, "// "))
    out.append("//")
    out.append("// Import and use:")
    out.append("//   local u = import 'hep/units.libsonnet';")
    out.append("//   { drift_time: u.cm / u.parse('1.6 mm/us') }")
    out.append("{")
    for (section, kind), syms in _grouped(records):
        label = section or ""
        tag = "" if kind == "unit" else " (constants)"
        out.append(f"  // ---- {label}{tag} ----")
        for sym in syms:
            rhs = render_expr(sym.expr, lambda n: "self." + n, jsonnet=True)
            out.append(f"  {sym.name}:: {rhs},  // = {_num(sym.value)}")
        out.append("")
    out.append("  // Names of every symbol (units and constants), in order.")
    out.append("  names:: [")
    for s in records:
        out.append(f"    '{s.name}',")
    out.append("  ],")
    out.append("")
    out.append("  // Lookup table { name: value } of every named symbol.  '$'")
    out.append("  // (this file's root object) is used so the comprehension's")
    out.append("  // 'self' rebinding does not shadow the unit fields.")
    out.append("  table:: { [n]: $[n] for n in $.names },")
    out.append(_JSONNET_PARSE.rstrip("\n"))
    out.append("}")
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Driver.
# --------------------------------------------------------------------------

def main(argv=None):
    here = Path(__file__).resolve().parent
    root = here.parent
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="*", type=Path,
                    default=[root / "units" / "clhep.units",
                             root / "units" / "hep.units"],
                    help="source-of-truth .units files (in consumption order)")
    ap.add_argument("--hpp", type=Path, default=root / "include" / "hep" / "units.hpp")
    ap.add_argument("--py", type=Path, default=root / "src" / "hep_units" / "__init__.py")
    ap.add_argument("--jsonnet", type=Path,
                    default=root / "jsonnet" / "hep" / "units.libsonnet")
    args = ap.parse_args(argv)

    records = parse_sources(args.sources)
    names = [p.name for p in args.sources]

    products = {
        args.hpp: emit_cpp(records, names),
        args.py: emit_python(records, names),
        args.jsonnet: emit_jsonnet(records, names),
    }
    for path, text in products.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print(f"wrote {path}  ({len(records)} symbols)")


if __name__ == "__main__":
    main()

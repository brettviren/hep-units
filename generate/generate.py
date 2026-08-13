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

// Resolve one atom: a numeric literal or a known symbol name.
inline double resolve(const std::string& atom)
{
  char* end = nullptr;
  const double v = std::strtod(atom.c_str(), &end);
  if (end != atom.c_str() && *end == '\0') {
    return v;  // it was a number
  }
  const auto it = table().find(atom);
  if (it == table().end()) {
    throw std::invalid_argument("hep::units::parse: unknown unit '" + atom + "'");
  }
  return it->second;
}

// ------------------------------------------------------------------------
// parse() -- evaluate a "value and units" string in the system of units.
//
// The string is a flat product/quotient of factors, each an optional integer
// power:
//
//     "1.5*cm"     "9.8 m/s^2"     "3 mm*ns"     "2*pi"     "eplus"
//
// Whitespace between two factors means multiplication.  Operators '*', '/' and
// '^' (or '**' for power) are honoured left-to-right; '^' binds to the factor
// on its left.  Factors are numeric literals or names from table().
// ------------------------------------------------------------------------
inline double parse(std::string_view text)
{
  std::string s(text);
  const auto replace_all = [](std::string& in, const std::string& from,
                              const std::string& to) {
    for (std::size_t p = in.find(from); p != std::string::npos;
         p = in.find(from, p + to.size())) {
      in.replace(p, from.size(), to);
    }
  };
  replace_all(s, "**", " ^ ");
  replace_all(s, "*", " * ");
  replace_all(s, "/", " / ");
  replace_all(s, "^", " ^ ");

  std::vector<std::string> toks;
  std::istringstream iss(s);
  for (std::string tk; iss >> tk;) {
    toks.push_back(tk);
  }
  if (toks.empty()) {
    throw std::invalid_argument("hep::units::parse: empty expression");
  }

  double acc = 1.0;
  char op = '*';
  for (std::size_t i = 0; i < toks.size();) {
    if (toks[i] == "*" || toks[i] == "/") {
      op = toks[i][0];
      ++i;
      continue;
    }
    double v = resolve(toks[i]);
    ++i;
    while (i < toks.size() && toks[i] == "^") {
      ++i;
      if (i >= toks.size()) {
        throw std::invalid_argument("hep::units::parse: dangling '^'");
      }
      v = std::pow(v, resolve(toks[i]));
      ++i;
    }
    acc = (op == '/') ? acc / v : acc * v;
    op = '*';  // adjacent factors multiply
  }
  return acc;
}
"""


def emit_cpp(records, sources):
    out = []
    out.extend(_header_lines(sources, "// "))
    out.append("")
    out.append("#pragma once")
    out.append("")
    out.append("#include <cmath>")
    out.append("#include <cstdlib>")
    out.append("#include <sstream>")
    out.append("#include <stdexcept>")
    out.append("#include <string>")
    out.append("#include <string_view>")
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


def _resolve(atom):
    try:
        return float(atom)
    except ValueError:
        pass
    if atom in TABLE:
        return TABLE[atom]
    raise ValueError(f"hep_units.parse: unknown unit {atom!r}")


def parse(text):
    """Evaluate a "value and units" string in the system of units.

    The string is a flat product/quotient of factors, each an optional integer
    power::

        parse("1.5*cm")     parse("9.8 m/s^2")     parse("3 mm*ns")
        parse("2*pi")       parse("eplus")

    Whitespace between two factors means multiplication.  Operators ``*``,
    ``/`` and ``^`` (or ``**`` for power) are honoured left-to-right; ``^``
    binds to the factor on its left.  Factors are numeric literals or names
    from :data:`TABLE`.
    """
    s = (text.replace("**", " ^ ").replace("*", " * ")
             .replace("/", " / ").replace("^", " ^ "))
    toks = s.split()
    if not toks:
        raise ValueError("hep_units.parse: empty expression")
    acc = 1.0
    op = "*"
    i = 0
    n = len(toks)
    while i < n:
        t = toks[i]
        if t in ("*", "/"):
            op = t
            i += 1
            continue
        v = _resolve(t)
        i += 1
        while i < n and toks[i] == "^":
            i += 1
            if i >= n:
                raise ValueError("hep_units.parse: dangling '^'")
            v = v ** _resolve(toks[i])
            i += 1
        acc = acc / v if op == "/" else acc * v
        op = "*"  # adjacent factors multiply
    return acc
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
  // Resolve one atom: a numeric literal or a known symbol name.  Symbol values
  // are looked up as fields of this object (self), which is also what table
  // enumerates.
  resolve(atom)::
    local c = std.substr(atom, 0, 1);
    if c == '.' || c == '-' || c == '+'
       || (std.codepoint(c) >= 48 && std.codepoint(c) <= 57)
    then std.parseJson(atom)
    else if std.objectHasAll(self, atom) then self[atom]
    else error 'hep_units.parse: unknown unit ' + atom,

  // parse(text) -- evaluate a "value and units" string in the system of units.
  //
  //   u.parse('1.5*cm')   u.parse('9.8 m/s^2')   u.parse('3 mm*ns')
  //   u.parse('2*pi')     u.parse('eplus')
  //
  // Whitespace between two factors means multiplication.  Operators '*', '/'
  // and '^' (or '**' for power) are honoured left-to-right; '^' binds to the
  // factor on its left.  Numeric literals must be valid JSON numbers (write
  // '1.0e-6', not '1.e-6').
  parse(text)::
    local root = self;  // pin the units object; 'self' rebinds inside {} below
    local s0 = std.strReplace(text, '**', ' ^ ');
    local s1 = std.strReplace(s0, '*', ' * ');
    local s2 = std.strReplace(s1, '/', ' / ');
    local s3 = std.strReplace(s2, '^', ' ^ ');
    local toks = std.filter(function(t) t != '', std.split(s3, ' '));
    if std.length(toks) == 0 then
      error 'hep_units.parse: empty expression'
    else
      // Read a factor (atom with optional '^ exponent') at index i.
      // Returns { value, next }.
      local readFactor(i) =
        local v0 = root.resolve(toks[i]);
        if i + 1 < std.length(toks) && toks[i + 1] == '^' then
          { value: std.pow(v0, root.resolve(toks[i + 2])), next: i + 3 }
        else
          { value: v0, next: i + 1 };
      // Left-to-right fold over factors and '*'/'/' operators.
      local loop(i, acc, op) =
        if i >= std.length(toks) then acc
        else if toks[i] == '*' || toks[i] == '/' then loop(i + 1, acc, toks[i])
        else
          local f = readFactor(i);
          local acc2 = if op == '/' then acc / f.value else acc * f.value;
          loop(f.next, acc2, '*');  // adjacent factors multiply
      loop(0, 1.0, '*'),
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

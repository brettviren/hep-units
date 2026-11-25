# Copyright (c) 2026, Brookhaven Science Associates, LLC
# SPDX-License-Identifier: Apache-2.0
"""parse() gives bit-identical results in C++, Python, Jsonnet and JavaScript.

Usage: test_parity.py EVAL_EXE JSONNET_EXE JSONNET_DIR [NODE_EXE]

Every case of parse-cases.txt is evaluated by each product: the values must
agree exactly (as hex floats) and an expression must be rejected by all of
them or by none.  JavaScript is included when NODE_EXE is given.
"""

import json
import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent / "src"))
import hep_units as u  # noqa: E402

from test_python import load_cases  # noqa: E402


def python_value(expr, syms):
    try:
        return float(u.parse(expr, syms)).hex()
    except ValueError:
        return "error"


def cpp_values(exe, cases):
    text = "".join(f"{e}|{';'.join(f'{k}={v!r}' for k, v in s.items())}\n" for e, s, _ in cases)
    out = subprocess.run([exe], input=text, capture_output=True, text=True, check=True).stdout
    return [line if line == "error" else float.fromhex(line).hex() for line in out.splitlines()]


def jsonnet_value(jsonnet, jdir, expr, syms):
    code = "local u = import 'hep/units.libsonnet'; u.parse(%s, %s)" % (json.dumps(expr), json.dumps(syms))
    r = subprocess.run([jsonnet, "-J", jdir, "-e", code], capture_output=True, text=True)
    if r.returncode != 0:
        return "error"
    return float(json.loads(r.stdout)).hex()


def js_values(node, cases):
    script = here / "hep_units_eval.js"
    text = "".join(f"{e}|{';'.join(f'{k}={v!r}' for k, v in s.items())}\n" for e, s, _ in cases)
    out = subprocess.run([node, str(script)], input=text, capture_output=True, text=True,
                         check=True).stdout
    return [line if line == "error" else float(line).hex() for line in out.splitlines()]


def js_table_mismatches(node):
    """Names whose JavaScript value differs from Python's in any bit."""
    code = ("const u = require(%s); console.log(JSON.stringify(u.NAMES.map(n => [n, u[n]])))"
            % json.dumps(str(here.parent / "js" / "hep-units.js")))
    out = subprocess.run([node, "-e", code], capture_output=True, text=True, check=True).stdout
    pairs = json.loads(out)
    bad = [n for n, v in pairs if float(v).hex() != float(u.TABLE.get(n, "nan")).hex()]
    if [n for n, _ in pairs] != list(u.TABLE):
        bad.append("<names differ>")
    return bad


def main(exe, jsonnet, jdir, node=None):
    cases = load_cases()
    cpp = cpp_values(exe, cases)
    js = js_values(node, cases) if node else [None] * len(cases)
    bad = 0
    if node:
        for name in js_table_mismatches(node):
            bad += 1
            print(f"MISMATCH table value {name}: Python vs JavaScript")
    for (expr, syms, _), c, s in zip(cases, cpp, js):
        p = python_value(expr, syms)
        j = jsonnet_value(jsonnet, jdir, expr, syms)
        if not (p == c == j) or (node and s != p):
            bad += 1
            print(f"MISMATCH {expr!r} {syms}: C++ {c}  Python {p}  Jsonnet {j}  JavaScript {s}")
    names = "C++, Python, Jsonnet" + (", JavaScript" if node else "")
    print(f"{len(cases)} cases ({names}), {bad} mismatch(es)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:5]))

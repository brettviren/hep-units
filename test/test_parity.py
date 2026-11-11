# Copyright (c) 2026, Brookhaven Science Associates, LLC
# SPDX-License-Identifier: Apache-2.0
"""parse() gives bit-identical results in C++, Python and Jsonnet.

Usage: test_parity.py EVAL_EXE JSONNET_EXE JSONNET_DIR

Every case of parse-cases.txt is evaluated by the three products: the values
must agree exactly (as hex floats) and an expression must be rejected by all
three or by none.
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


def main(exe, jsonnet, jdir):
    cases = load_cases()
    cpp = cpp_values(exe, cases)
    bad = 0
    for (expr, syms, _), c in zip(cases, cpp):
        p = python_value(expr, syms)
        j = jsonnet_value(jsonnet, jdir, expr, syms)
        if not (p == c == j):
            bad += 1
            print(f"MISMATCH {expr!r} {syms}: C++ {c}  Python {p}  Jsonnet {j}")
    print(f"{len(cases)} cases, {bad} mismatch(es)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))

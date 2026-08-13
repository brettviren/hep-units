# Copyright (c) 2026, Brookhaven Science Associates, LLC
# SPDX-License-Identifier: Apache-2.0
"""Sanity checks for the generated Python module (also runnable under pytest)."""

import math
import sys
from pathlib import Path

# Allow running against the in-tree source without installing.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import hep_units as u


def test_named_values():
    assert u.cm == 10.0
    assert u.m == 1000.0
    assert u.mm == 1.0
    assert u.ns == 1.0
    assert u.eplus == 1.0
    assert math.isclose(u.degree, math.pi / 180.0)
    assert math.isclose(u.twopi, 2 * math.pi)
    assert math.isclose(u.c_light, 299.792458)


def test_parse_coefficient_and_unit():
    assert u.parse("1.5*cm") == 15.0
    assert u.parse("1.5 cm") == 15.0          # implicit multiply
    assert u.parse("cm") == u.cm
    assert u.parse("2*pi") == u.twopi
    assert u.parse("eplus") == 1.0


def test_parse_compound():
    assert math.isclose(u.parse("9.8 m/s^2"), 9.8 * u.m / (u.s * u.s))
    assert math.isclose(u.parse("1.6 mm/us"), 1.6 * u.mm / u.us)
    assert math.isclose(u.parse("3 mm*ns"), 3 * u.mm * u.ns)
    assert math.isclose(u.parse("1/s"), 1.0 / u.s)


def test_table():
    assert len(u.TABLE) > 100
    assert u.TABLE["cm"] == u.cm


def test_unknown_unit_raises():
    try:
        u.parse("1.0 furlong")
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown unit")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
    print("all Python checks passed")

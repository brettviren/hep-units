// Copyright (c) 2026, Brookhaven Science Associates, LLC
// SPDX-License-Identifier: Apache-2.0
//
// Read lines "expression|name=value;name=value" from stdin and print, per
// line, hep::units::parse()'s value as a C99 hex float ("%a", exact), or
// "error".  Used by test_parity.py to compare C++, Python and Jsonnet.
#include "hep/units.hpp"

#include <cstdio>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>

int main()
{
  for (std::string line; std::getline(std::cin, line);) {
    const auto bar = line.find('|');
    const std::string expr = line.substr(0, bar);
    std::unordered_map<std::string, double> symbols;
    if (bar != std::string::npos) {
      std::string rest = line.substr(bar + 1);
      std::size_t b = 0;
      while (b < rest.size()) {
        auto e = rest.find(';', b);
        if (e == std::string::npos) { e = rest.size(); }
        const std::string kv = rest.substr(b, e - b);
        const auto eq = kv.find('=');
        if (eq != std::string::npos) {
          symbols[kv.substr(0, eq)] = std::stod(kv.substr(eq + 1));
        }
        b = e + 1;
      }
    }
    try {
      std::printf("%a\n", hep::units::parse(expr, symbols));
    }
    catch (const std::invalid_argument&) {
      std::printf("error\n");
    }
  }
  return 0;
}

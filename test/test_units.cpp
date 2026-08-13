// Basic sanity checks for the generated C++ header.
#include "dune/units.hpp"

#include <cmath>
#include <cstdio>
#include <string>

static int failures = 0;

static void check_close(const char* what, double got, double want)
{
  const double tol = 1e-9 * (1.0 + std::fabs(want));
  if (std::fabs(got - want) > tol) {
    std::printf("FAIL %s: got %.17g want %.17g\n", what, got, want);
    ++failures;
  }
}

int main()
{
  using namespace dune::units;

  // Named symbols carry the CLHEP values.
  check_close("cm", cm, 10.0);
  check_close("m", m, 1000.0);
  check_close("mm", mm, 1.0);
  check_close("ns", ns, 1.0);
  check_close("eplus", eplus, 1.0);
  check_close("degree", degree, pi / 180.0);
  check_close("twopi", twopi, 2 * pi);

  // parse(): coefficient * unit, explicit and implicit multiply.
  check_close("parse 1.5*cm", parse("1.5*cm"), 15.0);
  check_close("parse 1.5 cm", parse("1.5 cm"), 15.0);
  check_close("parse cm", parse("cm"), cm);
  check_close("parse 2*pi", parse("2*pi"), twopi);
  check_close("parse eplus", parse("eplus"), 1.0);

  // Compound with division and power.
  check_close("parse 9.8 m/s^2", parse("9.8 m/s^2"), 9.8 * m / (s * s));
  check_close("parse 1.6 mm/us", parse("1.6 mm/us"), 1.6 * mm / us);
  check_close("parse 3 mm*ns", parse("3 mm*ns"), 3 * mm * ns);
  check_close("parse 1/s", parse("1/s"), 1.0 / s);

  // The table holds every named symbol.
  if (table().size() < 100) {
    std::printf("FAIL table size unexpectedly small: %zu\n", table().size());
    ++failures;
  }

  if (failures) {
    std::printf("%d failure(s)\n", failures);
    return 1;
  }
  std::printf("all C++ checks passed\n");
  return 0;
}

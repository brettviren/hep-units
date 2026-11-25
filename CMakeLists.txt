# Copyright (c) 2026, Brookhaven Science Associates, LLC
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.25)
project(hep_units VERSION 0.2.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# hep-units ships four GENERATED products built from a single source of truth
# (the units/*.units files):
#
#   include/hep/units.hpp        -- C++17 header-only library
#   src/hep_units/__init__.py    -- Python module
#   jsonnet/hep/units.libsonnet  -- Jsonnet library
#   js/hep-units.js              -- JavaScript module (UMD)
#
# The products are committed to the repository; this build only installs them.
# Regenerate after editing a .units source with `python generate/generate.py`
# (or the `regenerate` target below).  The generator needs nothing but the
# Python standard library, so no build-time dependency is exposed here.

# ---------------------------------------------------------------------------
# hep_units -- header-only INTERFACE library (the C++ product).
# ---------------------------------------------------------------------------
add_library(hep_units INTERFACE)
add_library(hep_units::hep_units ALIAS hep_units)
target_include_directories(hep_units
  INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_compile_features(hep_units INTERFACE cxx_std_17)

# ---------------------------------------------------------------------------
# regenerate -- developer convenience to rebuild the committed products.
# Not part of the default build; run explicitly (`cmake --build . --target
# regenerate`) after editing a units/*.units source.
# ---------------------------------------------------------------------------
find_package(Python3 COMPONENTS Interpreter)
if(Python3_Interpreter_FOUND)
  add_custom_target(regenerate
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/generate/generate.py
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    COMMENT "Regenerating hep-units products from units/*.units"
    VERBATIM)

  # docs -- the Markdown documentation in docs/ as a static HTML web area in
  # <build>/docs (needs pandoc, or the Python "markdown" package).
  add_custom_target(docs
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/docs/build.py -o ${CMAKE_CURRENT_BINARY_DIR}/docs
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    COMMENT "Building the HTML documentation in ${CMAKE_CURRENT_BINARY_DIR}/docs"
    VERBATIM)
endif()

enable_testing()
add_subdirectory(test)

# ---------------------------------------------------------------------------
# Install: C++ header, Python module, Jsonnet library, JavaScript module.
# ---------------------------------------------------------------------------
include(GNUInstallDirs)

install(TARGETS hep_units EXPORT hep_unitsTargets)

# C++ header -> <prefix>/include/hep/units.hpp
install(DIRECTORY include/hep
  DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
  FILES_MATCHING PATTERN "*.hpp"
)

# Python module -> <prefix>/python/hep_units/__init__.py
# (put <prefix>/python on PYTHONPATH; the parallel pyproject.toml is the
# primary, packaging-native way to install the same single file.)
install(DIRECTORY src/hep_units
  DESTINATION python
  FILES_MATCHING PATTERN "*.py"
)

# Jsonnet library -> <prefix>/share/jsonnet/hep/units.libsonnet
# (put <prefix>/share/jsonnet on the Jsonnet library search path so it imports
# as "hep/units.libsonnet".)
install(DIRECTORY jsonnet/hep
  DESTINATION "${CMAKE_INSTALL_DATADIR}/jsonnet"
  FILES_MATCHING PATTERN "*.libsonnet"
)

# JavaScript module -> <prefix>/share/javascript/hep-units.js
# (a UMD file: load with <script>, require() or import; the parallel
# package.json lets npm install the same single file.)
install(FILES js/hep-units.js
  DESTINATION "${CMAKE_INSTALL_DATADIR}/javascript"
)

# CMake package config so downstreams can find_package(hep_units).
install(EXPORT hep_unitsTargets
  FILE hep_unitsTargets.cmake
  NAMESPACE hep_units::
  DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/hep_units"
)
include(CMakePackageConfigHelpers)
write_basic_package_version_file(
  "${CMAKE_CURRENT_BINARY_DIR}/hep_unitsConfigVersion.cmake"
  VERSION "${PROJECT_VERSION}"
  COMPATIBILITY SameMajorVersion
)
configure_package_config_file(
  "${CMAKE_CURRENT_SOURCE_DIR}/cmake/hep_unitsConfig.cmake.in"
  "${CMAKE_CURRENT_BINARY_DIR}/hep_unitsConfig.cmake"
  INSTALL_DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/hep_units"
)
install(FILES
  "${CMAKE_CURRENT_BINARY_DIR}/hep_unitsConfig.cmake"
  "${CMAKE_CURRENT_BINARY_DIR}/hep_unitsConfigVersion.cmake"
  DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/hep_units"
)

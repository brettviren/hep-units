cmake_minimum_required(VERSION 3.25)
project(dune_units VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# dune-units ships three GENERATED products built from a single source of truth
# (the units/*.units files):
#
#   include/dune/units.hpp        -- C++17 header-only library
#   src/dune_units/__init__.py    -- Python module
#   jsonnet/dune/units.libsonnet  -- Jsonnet library
#
# The products are committed to the repository; this build only installs them.
# Regenerate after editing a .units source with `python generate/generate.py`
# (or the `regenerate` target below).  The generator needs nothing but the
# Python standard library, so no build-time dependency is exposed here.

# ---------------------------------------------------------------------------
# dune_units -- header-only INTERFACE library (the C++ product).
# ---------------------------------------------------------------------------
add_library(dune_units INTERFACE)
add_library(dune_units::dune_units ALIAS dune_units)
target_include_directories(dune_units
  INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_compile_features(dune_units INTERFACE cxx_std_17)

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
    COMMENT "Regenerating dune-units products from units/*.units"
    VERBATIM)
endif()

enable_testing()
add_subdirectory(test)

# ---------------------------------------------------------------------------
# Install: C++ header, Python module, Jsonnet library.
# ---------------------------------------------------------------------------
include(GNUInstallDirs)

install(TARGETS dune_units EXPORT dune_unitsTargets)

# C++ header -> <prefix>/include/dune/units.hpp
install(DIRECTORY include/dune
  DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
  FILES_MATCHING PATTERN "*.hpp"
)

# Python module -> <prefix>/python/dune_units/__init__.py
# (put <prefix>/python on PYTHONPATH; the parallel pyproject.toml is the
# primary, packaging-native way to install the same single file.)
install(DIRECTORY src/dune_units
  DESTINATION python
  FILES_MATCHING PATTERN "*.py"
)

# Jsonnet library -> <prefix>/share/jsonnet/dune/units.libsonnet
# (put <prefix>/share/jsonnet on the Jsonnet library search path so it imports
# as "dune/units.libsonnet".)
install(DIRECTORY jsonnet/dune
  DESTINATION "${CMAKE_INSTALL_DATADIR}/jsonnet"
  FILES_MATCHING PATTERN "*.libsonnet"
)

# CMake package config so downstreams can find_package(dune_units).
install(EXPORT dune_unitsTargets
  FILE dune_unitsTargets.cmake
  NAMESPACE dune_units::
  DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/dune_units"
)
include(CMakePackageConfigHelpers)
write_basic_package_version_file(
  "${CMAKE_CURRENT_BINARY_DIR}/dune_unitsConfigVersion.cmake"
  VERSION "${PROJECT_VERSION}"
  COMPATIBILITY SameMajorVersion
)
configure_package_config_file(
  "${CMAKE_CURRENT_SOURCE_DIR}/cmake/dune_unitsConfig.cmake.in"
  "${CMAKE_CURRENT_BINARY_DIR}/dune_unitsConfig.cmake"
  INSTALL_DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/dune_units"
)
install(FILES
  "${CMAKE_CURRENT_BINARY_DIR}/dune_unitsConfig.cmake"
  "${CMAKE_CURRENT_BINARY_DIR}/dune_unitsConfigVersion.cmake"
  DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/dune_units"
)

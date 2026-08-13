# Copyright (c) 2026, Brookhaven Science Associates, LLC
# SPDX-License-Identifier: Apache-2.0
# C++ test of the generated header.
add_executable(test_units test_units.cpp)
target_link_libraries(test_units PRIVATE hep_units::hep_units)
target_compile_options(test_units PRIVATE -Wall -Wpedantic -Werror)
add_test(NAME cpp_units COMMAND test_units)

# Python test of the generated module (uses only the standard library).
find_package(Python3 COMPONENTS Interpreter)
if(Python3_Interpreter_FOUND)
  add_test(NAME python_units
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_python.py)
endif()

# Jsonnet test of the generated library, if a jsonnet CLI is available.
find_program(JSONNET_EXECUTABLE NAMES jsonnet)
if(JSONNET_EXECUTABLE)
  add_test(NAME jsonnet_units
    COMMAND ${JSONNET_EXECUTABLE}
            -J ${CMAKE_CURRENT_SOURCE_DIR}/../jsonnet
            ${CMAKE_CURRENT_SOURCE_DIR}/test_jsonnet.jsonnet)
endif()

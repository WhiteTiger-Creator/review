#!/bin/bash
set -euo pipefail

TOP=/app/pipeline/CMakeLists.txt
SRC=/app/pipeline/src/CMakeLists.txt

sed -i 's#/app/docs/samples#/app/docs/pages#' "$TOP"

sed -i 's/pinsel_latest\.c/pinsel_floor.c/' "$SRC"
sed -i 's/fold_none\.c/fold_alias.c/' "$SRC"
sed -i 's/sevagg_max\.c/sevagg_curated.c/' "$SRC"
sed -i 's/order_name\.c/order_weighted.c/' "$SRC"
sed -i 's/RISK_SCHEMA_VERSION="3"/RISK_SCHEMA_VERSION="4"/' "$SRC"

sed -i 's#${CMAKE_CURRENT_SOURCE_DIR}/compat ##' "$SRC"
sed -i 's#target_include_directories(score PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})#target_include_directories(score PRIVATE ${CMAKE_BINARY_DIR}/generated ${CMAKE_CURRENT_SOURCE_DIR})#' "$SRC"

cat >> "$SRC" <<'EOF'

add_custom_command(OUTPUT ${CMAKE_BINARY_DIR}/generated/severity_table.h
  COMMAND ${CMAKE_COMMAND} -E make_directory ${CMAKE_BINARY_DIR}/generated
  COMMAND $<TARGET_FILE:mkscore> ${CMAKE_SOURCE_DIR}/config/severity.map ${CMAKE_BINARY_DIR}/generated/severity_table.h
  DEPENDS mkscore ${CMAKE_SOURCE_DIR}/config/severity.map)
add_custom_target(gen_severity DEPENDS ${CMAKE_BINARY_DIR}/generated/severity_table.h)
add_dependencies(score gen_severity)
EOF

rm -rf /app/build
cmake -S /app/pipeline -B /app/build
cmake --build /app/build --target report

test -s /app/out/risk-report.json
grep -q '"schema_version": "4"' /app/out/risk-report.json
grep -q '"max_severity": 5.4' /app/out/risk-report.json

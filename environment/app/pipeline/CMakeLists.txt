cmake_minimum_required(VERSION 3.16)
project(riskpipe C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

add_subdirectory(vendor/qjson)
add_subdirectory(src)
add_subdirectory(tools)

add_custom_target(report
  COMMAND $<TARGET_FILE:extract> /app/docs/samples ${CMAKE_BINARY_DIR}/packages.tsv
  COMMAND $<TARGET_FILE:advise> ${CMAKE_BINARY_DIR}/packages.tsv /var/lib/osv ${CMAKE_BINARY_DIR}/matches.json
  COMMAND $<TARGET_FILE:score> ${CMAKE_BINARY_DIR}/matches.json /app/out/risk-report.json
  DEPENDS extract advise score)

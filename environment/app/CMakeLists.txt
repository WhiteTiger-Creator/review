cmake_minimum_required(VERSION 3.20)
project(qr_composer C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

add_compile_options(-Wall -Wextra -O2)

include_directories(${CMAKE_SOURCE_DIR}/include)

add_executable(qr-composer
  src/core/main.c
  src/core/util.c
  src/core/sha256.c
  src/core/tables.c
  src/core/config.c
  src/ingest/ingest_shipbatches.c
  src/plan/segment_plan.c
  src/assemble/assemble_codewords.c
  src/protect/gf256.c
  src/protect/protect_blocks.c
  src/interleave/interleave_streams.c
  src/matrix/matrix_build.c
  src/tournament/penalty_rules.c
  src/tournament/run_tournament.c
  src/emit/emit_labels.c
)

add_library(decoy_code128 STATIC vendor/decoy_code128/decoy_code128.c)

cmake_minimum_required(VERSION 3.18)
project(termatrix VERSION 2.4.0 LANGUAGES C CXX)
list(APPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake/modules")
include(TermatrixInstall)
include(TermatrixAudit)

if(NOT DEFINED TERMATRIX_TARGET_NAME OR NOT DEFINED TERMATRIX_ABI_FAMILY)
  message(FATAL_ERROR "TERMATRIX_TARGET_NAME and TERMATRIX_ABI_FAMILY must come from a matrix toolchain file")
endif()

if(NOT DEFINED TERMATRIX_ABI_DEFINE OR NOT DEFINED TERMATRIX_TARGET_DEFINE)
  message(FATAL_ERROR "ABI and target compile definitions must come from the matrix toolchain file")
endif()

if(NOT DEFINED TERMATRIX_DRIVER OR NOT EXISTS "${TERMATRIX_DRIVER}")
  message(FATAL_ERROR "TERMATRIX_DRIVER must point to the compiled matrix driver")
endif()

if(NOT DEFINED TERMATRIX_DESCRIPTOR_FILE OR NOT EXISTS "${TERMATRIX_DESCRIPTOR_FILE}")
  message(FATAL_ERROR "TERMATRIX_DESCRIPTOR_FILE must point to the active matrix descriptor")
endif()

set(TERMATRIX_CACHE_ROOT "${CMAKE_SOURCE_DIR}/../.termatrix-cache" CACHE PATH "Termatrix object cache root")
file(MAKE_DIRECTORY "${TERMATRIX_CACHE_ROOT}")
file(GLOB_RECURSE TERMATRIX_HEADERS CONFIGURE_DEPENDS "${CMAKE_SOURCE_DIR}/include/*.h")
file(GLOB TERMATRIX_ENGINE_SOURCES CONFIGURE_DEPENDS
  "${CMAKE_SOURCE_DIR}/engine/*.cpp"
  "${CMAKE_SOURCE_DIR}/engine/*.hpp"
)

set(TERMATRIX_UNIT_NAMES identity mix)
set(TERMATRIX_UNIT_identity_SOURCE "src/identity.c")
set(TERMATRIX_UNIT_mix_SOURCE "src/mix.c")
set(TERMATRIX_CACHED_OBJECTS "")
set(TERMATRIX_CACHED_METAS "")

foreach(unit_name IN LISTS TERMATRIX_UNIT_NAMES)
  set(unit_source "${TERMATRIX_UNIT_${unit_name}_SOURCE}")
  execute_process(
    COMMAND "${TERMATRIX_DRIVER}" key-unit
            "${CMAKE_SOURCE_DIR}"
            "${unit_name}"
            "${unit_source}"
            "${TERMATRIX_TARGET_NAME}"
    OUTPUT_VARIABLE TERMATRIX_CACHE_KEY_RAW
    ERROR_VARIABLE TERMATRIX_CACHE_KEY_ERR
    RESULT_VARIABLE TERMATRIX_CACHE_KEY_STATUS
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )
  if(NOT TERMATRIX_CACHE_KEY_STATUS EQUAL 0)
    message(FATAL_ERROR "cache key calculation failed for ${unit_name}: ${TERMATRIX_CACHE_KEY_ERR}")
  endif()
  string(REGEX REPLACE "[^0-9a-f]" "" TERMATRIX_CACHE_KEY "${TERMATRIX_CACHE_KEY_RAW}")
  termatrix_require_cache_key("${TERMATRIX_CACHE_KEY}")

  set(cache_slot "${TERMATRIX_CACHE_ROOT}/${unit_name}-${TERMATRIX_CACHE_KEY}")
  set(cache_object "${cache_slot}/${unit_name}.o")
  set(cache_meta "${cache_slot}/${unit_name}.meta")
  add_custom_command(
    OUTPUT "${cache_object}"
    BYPRODUCTS "${cache_meta}"
    COMMAND "${TERMATRIX_DRIVER}" compile-unit
            "${CMAKE_C_COMPILER}"
            "${cache_object}"
            "${CMAKE_SOURCE_DIR}"
            "${unit_name}"
            "${unit_source}"
            "${TERMATRIX_TARGET_NAME}"
            "${TERMATRIX_ABI_FAMILY}"
            "${TERMATRIX_ABI_DEFINE}"
            "${TERMATRIX_TARGET_DEFINE}"
            "${TERMATRIX_CACHE_KEY}"
            "${CMAKE_TOOLCHAIN_FILE}"
            "${TERMATRIX_DESCRIPTOR_FILE}"
            "${TERMATRIX_COMPILER_PROFILE}"
    DEPENDS
            "${CMAKE_SOURCE_DIR}/${unit_source}"
            ${TERMATRIX_HEADERS}
            ${TERMATRIX_ENGINE_SOURCES}
            "${CMAKE_SOURCE_DIR}/scripts/build_matrix.sh"
            "${CMAKE_SOURCE_DIR}/CMakeLists.txt"
            "${TERMATRIX_DESCRIPTOR_FILE}"
            "${CMAKE_TOOLCHAIN_FILE}"
    VERBATIM
  )
  list(APPEND TERMATRIX_CACHED_OBJECTS "${cache_object}")
  list(APPEND TERMATRIX_CACHED_METAS "${cache_meta}")
  set_source_files_properties("${cache_object}" PROPERTIES EXTERNAL_OBJECT TRUE GENERATED TRUE)
endforeach()

add_custom_target(termatrix_object_cache DEPENDS ${TERMATRIX_CACHED_OBJECTS})
add_library(termatrix STATIC ${TERMATRIX_CACHED_OBJECTS})
add_dependencies(termatrix termatrix_object_cache)
set_target_properties(termatrix PROPERTIES
  LINKER_LANGUAGE C
  ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/stage/lib"
  OUTPUT_NAME "termatrix"
)
target_include_directories(termatrix PUBLIC "${CMAKE_SOURCE_DIR}/include")

termatrix_install_layout(termatrix "${TERMATRIX_CACHED_METAS}")

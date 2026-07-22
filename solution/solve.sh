#!/bin/bash
set -euo pipefail

cat > /app/CMakeLists.txt <<'CMAKE'
cmake_minimum_required(VERSION 3.25)
project(RouteKit LANGUAGES CXX)

include(CMakePackageConfigHelpers)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(Protobuf REQUIRED)
find_package(gRPC REQUIRED)

set(GENERATED_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
set(PROTO_FILE "${CMAKE_CURRENT_SOURCE_DIR}/proto/route.proto")
file(MAKE_DIRECTORY "${GENERATED_DIR}")

set(GENERATED_SOURCES
  "${GENERATED_DIR}/route.pb.cc"
  "${GENERATED_DIR}/route.grpc.pb.cc")
set(GENERATED_HEADERS
  "${GENERATED_DIR}/route.pb.h"
  "${GENERATED_DIR}/route.grpc.pb.h")

add_custom_command(
  OUTPUT ${GENERATED_SOURCES} ${GENERATED_HEADERS}
  COMMAND protobuf::protoc
  ARGS --proto_path "${CMAKE_CURRENT_SOURCE_DIR}/proto"
       --cpp_out "${GENERATED_DIR}"
       --grpc_out "${GENERATED_DIR}"
       --plugin=protoc-gen-grpc=$<TARGET_FILE:gRPC::grpc_cpp_plugin>
       "${PROTO_FILE}"
  DEPENDS "${PROTO_FILE}"
  VERBATIM)

add_library(route_proto STATIC ${GENERATED_SOURCES} ${GENERATED_HEADERS})
target_include_directories(route_proto PUBLIC
  $<BUILD_INTERFACE:${GENERATED_DIR}>
  $<INSTALL_INTERFACE:include>)
target_link_libraries(route_proto PUBLIC protobuf::libprotobuf gRPC::grpc++)

add_library(router STATIC src/router.cpp)
target_include_directories(router PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_definitions(router PUBLIC ROUTER_BUILD_MODE="$<CONFIG>")
target_link_libraries(router PUBLIC route_proto)

add_library(route_policy SHARED src/policy.cpp)
target_include_directories(route_policy PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
set_target_properties(route_policy PROPERTIES INSTALL_RPATH "$ORIGIN")

add_library(route_audit SHARED plugins/audit.cpp)
target_link_libraries(route_audit PRIVATE router route_policy)
set_target_properties(route_audit PROPERTIES INSTALL_RPATH "$ORIGIN/..")

add_executable(route_cli src/main.cpp)
target_link_libraries(route_cli PRIVATE router dl)
set_target_properties(route_cli PROPERTIES INSTALL_RPATH "$ORIGIN/../lib")

install(TARGETS route_cli router route_proto route_policy
  EXPORT RouteKitTargets
  RUNTIME DESTINATION bin
  LIBRARY DESTINATION lib
  ARCHIVE DESTINATION lib)
install(TARGETS route_audit
  EXPORT RouteKitTargets
  LIBRARY DESTINATION lib/route)
install(DIRECTORY include/ DESTINATION include)
install(FILES ${GENERATED_HEADERS} DESTINATION include)
install(EXPORT RouteKitTargets
  NAMESPACE RouteKit::
  DESTINATION lib/cmake/RouteKit)
configure_package_config_file(
  "${CMAKE_CURRENT_SOURCE_DIR}/cmake/RouteKitConfig.cmake.in"
  "${CMAKE_CURRENT_BINARY_DIR}/RouteKitConfig.cmake"
  INSTALL_DESTINATION lib/cmake/RouteKit)
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/RouteKitConfig.cmake"
  DESTINATION lib/cmake/RouteKit)
CMAKE

mkdir -p /app/cmake
cat > /app/cmake/RouteKitConfig.cmake.in <<'CMAKE'
@PACKAGE_INIT@

include(CMakeFindDependencyMacro)
find_dependency(Protobuf REQUIRED)
find_dependency(gRPC REQUIRED)

include("${CMAKE_CURRENT_LIST_DIR}/RouteKitTargets.cmake")
CMAKE

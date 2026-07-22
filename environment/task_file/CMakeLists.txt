cmake_minimum_required(VERSION 3.25)
project(RouteKit LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Protobuf REQUIRED)
find_package(gRPC REQUIRED)

set(GENERATED_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
set(PROTO_FILE "${CMAKE_CURRENT_SOURCE_DIR}/proto/route.proto")
file(MAKE_DIRECTORY "${GENERATED_DIR}")

add_custom_command(
  OUTPUT
    "${GENERATED_DIR}/route.pb.cc"
    "${GENERATED_DIR}/route.pb.h"
    "${GENERATED_DIR}/route.grpc.pb.cc"
    "${GENERATED_DIR}/route.grpc.pb.h"
  COMMAND protobuf::protoc
  ARGS --proto_path "${CMAKE_CURRENT_SOURCE_DIR}/proto"
       --cpp_out "${GENERATED_DIR}"
       --grpc_out "${GENERATED_DIR}"
       --plugin=protoc-gen-grpc=$<TARGET_FILE:gRPC::grpc_cpp_plugin>
       "${PROTO_FILE}"
  VERBATIM)

add_library(route_proto STATIC
  "${GENERATED_DIR}/route.pb.cc"
  "${GENERATED_DIR}/route.grpc.pb.cc")
target_include_directories(route_proto PRIVATE "${GENERATED_DIR}")
target_link_libraries(route_proto PRIVATE protobuf::libprotobuf gRPC::grpc++)

add_library(router STATIC src/router.cpp)
target_include_directories(router PUBLIC include)
target_compile_definitions(router PRIVATE ROUTER_BUILD_MODE="$<CONFIG>")
target_link_libraries(router PRIVATE route_proto)

add_library(route_policy SHARED src/policy.cpp)
target_include_directories(route_policy PUBLIC include)

add_library(route_audit SHARED plugins/audit.cpp)
target_link_libraries(route_audit PRIVATE router route_policy)

add_executable(route_cli src/main.cpp)
target_link_libraries(route_cli PRIVATE router dl)

install(TARGETS route_cli router route_proto
  RUNTIME DESTINATION bin
  LIBRARY DESTINATION lib
  ARCHIVE DESTINATION lib)

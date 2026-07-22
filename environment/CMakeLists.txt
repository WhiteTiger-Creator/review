cmake_minimum_required(VERSION 3.16)
project(dense_svd_solver CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

file(GLOB SOLVER_IMPL_SOURCES CONFIGURE_DEPENDS "${CMAKE_SOURCE_DIR}/src/*.cpp")
list(REMOVE_ITEM SOLVER_IMPL_SOURCES "${CMAKE_SOURCE_DIR}/src/main_stub.cpp")
list(REMOVE_ITEM SOLVER_IMPL_SOURCES "${CMAKE_SOURCE_DIR}/src/smoke_test.cpp")

add_executable(svd_solve src/main_stub.cpp ${SOLVER_IMPL_SOURCES})
target_include_directories(svd_solve PRIVATE include src)
target_compile_options(svd_solve PRIVATE -Wall -Wextra)

add_executable(smoke_test src/smoke_test.cpp ${SOLVER_IMPL_SOURCES})
target_include_directories(smoke_test PRIVATE include src)
target_compile_options(smoke_test PRIVATE -Wall -Wextra)

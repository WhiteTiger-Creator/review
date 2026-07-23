cmake_minimum_required(VERSION 3.25)
project(site_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(site-core
    src/ctl/main.cc
    src/engine/session.cc
    src/store/ledger.cc
    src/fs/walker.cc
    src/model/record.cc
    src/support/codec.cc
    src/support/files.cc
    src/support/clock.cc
    src/observe/report.cc
)
target_include_directories(site-core PRIVATE src)
target_compile_options(site-core PRIVATE -Wall -Wextra -Wpedantic)
install(TARGETS site-core RUNTIME DESTINATION bin)

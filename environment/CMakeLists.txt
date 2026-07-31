cmake_minimum_required(VERSION 3.25)
project(hs_workspace LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(OpenSSL REQUIRED)
find_package(nlohmann_json 3.11.2 REQUIRED)

add_library(r3k_lib r3k/src/q2_w3.cpp r3k/src/decoy_h1.cpp)
target_include_directories(r3k_lib PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/r3k/include)

add_library(w7p_lib w7p/src/m5_norm.cpp w7p/src/reloc_fold.cpp w7p/src/decoy_h2.cpp)
target_include_directories(w7p_lib PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/w7p/include)

add_library(s4d_lib s4d/src/bank_cache.cpp)
target_include_directories(s4d_lib PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/s4d/include)
target_link_libraries(s4d_lib PUBLIC OpenSSL::Crypto)

add_library(j2n_lib j2n/src/v8_emit.cpp j2n/src/decoy_h3.cpp)
target_include_directories(j2n_lib PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/j2n/include)
target_link_libraries(j2n_lib PUBLIC OpenSSL::Crypto)

add_executable(hs_driver
  hs_driver/src/main.cpp
  hs_driver/src/corpus_stage.cpp
  hs_driver/src/lane_stage.cpp
  hs_driver/src/bundle_stage.cpp)
target_include_directories(hs_driver PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/hs_driver/include
  ${CMAKE_CURRENT_SOURCE_DIR}/r3k/include
  ${CMAKE_CURRENT_SOURCE_DIR}/w7p/include
  ${CMAKE_CURRENT_SOURCE_DIR}/j2n/include
  ${CMAKE_CURRENT_SOURCE_DIR}/s4d/include)
target_link_libraries(hs_driver PRIVATE r3k_lib w7p_lib j2n_lib s4d_lib nlohmann_json::nlohmann_json OpenSSL::Crypto)

install(TARGETS hs_driver RUNTIME DESTINATION bin)

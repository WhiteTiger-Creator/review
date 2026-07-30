project(regret_solver LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(regret_solver
  desk/DeskMain.cpp
  desk/CommonUtil.cpp
  stage_t/TraceIo.cpp
  desk/AnnexReader.cpp
  desk/BandGlue.cpp
  desk/BuildLocal.cpp
  desk/JournalGlue.cpp
  stage_p/WeaveSlot.cpp
  stage_p/DecoyWeave.cpp
  stage_q/SpliceBand.cpp
  stage_q/DecoySplice.cpp
  stage_r/SealRing.cpp
  stage_r/DecoySeal.cpp
  stage_j/ShardLedger.cpp
  stage_j/DecoyLedger.cpp
  stage_v/ExtProbe.cpp
  stage_v/DecoyProbe.cpp
)
target_include_directories(regret_solver PRIVATE
  ${CMAKE_SOURCE_DIR}
  ${CMAKE_SOURCE_DIR}/desk
  ${CMAKE_SOURCE_DIR}/stage_t
  ${CMAKE_SOURCE_DIR}/stage_p
  ${CMAKE_SOURCE_DIR}/stage_q
  ${CMAKE_SOURCE_DIR}/stage_r
  ${CMAKE_SOURCE_DIR}/stage_j
  ${CMAKE_SOURCE_DIR}/stage_v
)
find_package(nlohmann_json 3.2.0 REQUIRED)
target_link_libraries(regret_solver PRIVATE nlohmann_json::nlohmann_json)
find_package(OpenSSL REQUIRED)
target_link_libraries(regret_solver PRIVATE OpenSSL::Crypto)

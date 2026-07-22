add_executable(extract extract.c common.c vercmp.c pinsel_latest.c)
add_executable(advise advise.c common.c vercmp.c)
add_executable(score score.c common.c cvss.c fold_none.c sevagg_max.c order_name.c)

target_compile_definitions(score PRIVATE RISK_SCHEMA_VERSION="3")

foreach(tool extract advise)
  target_include_directories(${tool} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/compat ${CMAKE_CURRENT_SOURCE_DIR})
endforeach()
target_include_directories(score PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

target_link_libraries(advise qjson)
target_link_libraries(score qjson m)

add_library(qjson STATIC qjson.c)
target_include_directories(qjson PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

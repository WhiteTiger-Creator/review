add_library(core_b STATIC
    ../b07/v3_read_scale.c
    ../b07/j2_shadow.c
    ../b07/extra_b1.c
    ../b07/extra_b2.c
    ../b07/scan_bridge.c
)
add_library(core_f STATIC
    ../f12/k8_rank_slot.cpp
    ../f12/m4_shadow.cpp
    ../f12/extra_f1.cpp
    ../f12/extra_f2.cpp
    ../f12/lane_bridge.cpp
    ../f12/total_bridge.cpp
)
add_library(core_n STATIC
    ../n21/q5_pack_stamp.cpp
    ../n21/p1_shadow.cpp
    ../n21/extra_n1.cpp
    ../n21/extra_n2.cpp
    ../n21/pack_bridge.cpp
)
add_library(core_m STATIC
    ../m14/lane_store.cpp
    ../m14/extra_m1.cpp
    ../m14/shadow_m2.c
    ../m14/token_bridge.cpp
    ../m14/read_bridge.cpp
    ../m14/store_bridge.cpp
)
add_library(core_c STATIC
    ../c9/pass_gate.cpp
    ../c9/extra_c1.c
    ../c9/mode_bridge.cpp
)
target_include_directories(core_b PUBLIC ../include)
target_include_directories(core_f PUBLIC ../include)
target_include_directories(core_n PUBLIC ../include)
target_include_directories(core_m PUBLIC ../include)
target_include_directories(core_c PUBLIC ../include)
add_executable(forge_emit main.cpp emit_pipeline.cpp)
target_include_directories(forge_emit PRIVATE ../include)
target_link_libraries(forge_emit PRIVATE core_n core_f core_b core_m core_c)
set_target_properties(forge_emit PROPERTIES RUNTIME_OUTPUT_DIRECTORY /app/build)

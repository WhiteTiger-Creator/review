#pragma once

#include <filesystem>
#include <string>
#include <vector>

namespace termatrix {

inline constexpr const char *kGenerator = "termatrix-cmake-cache-matrix-v2";
inline constexpr int kSchemaVersion = 2;

struct Descriptor {
    std::string requested_name;
    std::string target_name;
    std::string abi_family;
    std::string abi_define;
    std::string target_define;
    std::string toolchain_file;
    std::string compiler_profile;
    std::filesystem::path descriptor_path;
};

struct UnitDef {
    std::string name;
    std::string source_rel;
};

struct UnitPreState {
    std::string unit;
    std::string key;
    bool hit = false;
    std::string reason;
};

inline std::vector<UnitDef> object_units() {
    return {
        {"identity", "src/identity.c"},
        {"mix", "src/mix.c"},
    };
}

inline std::vector<std::string> cache_key_fields() {
    return {
        "unit_source_sha256",
        "public_header_sha256",
        "descriptor_sha256",
        "toolchain_sha256",
        "build_logic_sha256",
        "target",
        "abi_family",
        "compiler_profile",
        "unit_name",
    };
}

}  // namespace termatrix

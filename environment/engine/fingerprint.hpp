#pragma once

#include "model.hpp"

#include <filesystem>
#include <string>

namespace termatrix {

std::string sha256_file(const std::filesystem::path &path);
std::string sha256_text(const std::string &text);
std::string tree_digest(const std::filesystem::path &root);
std::string build_logic_digest(const std::filesystem::path &root);
std::string cache_key_for_unit(
    const std::filesystem::path &root,
    const Descriptor &descriptor,
    const UnitDef &unit);

}  // namespace termatrix

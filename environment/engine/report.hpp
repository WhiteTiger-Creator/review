#pragma once

#include "model.hpp"

#include <filesystem>
#include <map>
#include <string>
#include <vector>

namespace termatrix {

std::map<std::string, std::string> read_meta_file(const std::filesystem::path &path);
void write_pkg_config(const std::filesystem::path &stage, const Descriptor &descriptor);
void write_identity_json(const std::filesystem::path &stage, const Descriptor &descriptor);
void write_cache_report(
    const std::filesystem::path &root,
    const std::filesystem::path &stage,
    const std::filesystem::path &cache_root,
    const Descriptor &descriptor,
    const std::vector<UnitPreState> &pre_states);
void write_top_report(
    const std::filesystem::path &out_root,
    const std::vector<std::string> &targets);

}  // namespace termatrix

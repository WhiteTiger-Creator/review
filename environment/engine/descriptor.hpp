#pragma once

#include "model.hpp"

#include <filesystem>
#include <string>
#include <vector>

namespace termatrix {

std::vector<std::string> parse_target_list();
Descriptor load_descriptor(const std::filesystem::path &root, const std::string &target);

}  // namespace termatrix

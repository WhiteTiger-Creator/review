#pragma once

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace site {

struct Scan {
    std::vector<std::string> paths;
    std::uint64_t fingerprint;
};

Scan observe_tree(const std::filesystem::path& root);
std::string render_scan(const Scan& scan);

}  // namespace site

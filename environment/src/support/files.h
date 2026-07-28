#pragma once

#include <filesystem>
#include <string>

namespace site {

std::string read_text(const std::filesystem::path& path);
void write_atomic(const std::filesystem::path& path, const std::string& text);
bool has_nonempty(const std::filesystem::path& path);

}  // namespace site

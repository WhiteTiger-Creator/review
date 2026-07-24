#pragma once

#include <filesystem>
#include <string>

namespace site {

std::string operator_view(const std::filesystem::path& root);
void append_event(const std::filesystem::path& root, const std::string& event);

}  // namespace site

#pragma once

#include <filesystem>
#include <string>

namespace site {

bool valid_root(const std::filesystem::path& root);
bool is_busy(const std::filesystem::path& root);
void replay_local(const std::filesystem::path& root);
void scan_local(const std::filesystem::path& root);
void stage_local(const std::filesystem::path& root);
void commit_local(const std::filesystem::path& root);
void seal_q(const std::filesystem::path& root);
bool serviceable(const std::filesystem::path& root);
std::string inspect_local(const std::filesystem::path& root);

}  // namespace site

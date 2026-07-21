#pragma once
#include "types.h"
#include <filesystem>
#include <string>
#include <vector>

const char *forge_lane_fingerprint(const forge::UnitSpec *units, size_t count);
forge::LaneCheckpoint forge_lane_load_checkpoint(const std::filesystem::path &path,
                                                 const std::string &expected_token);
std::vector<forge::UnitCheckpoint> forge_lane_merge_checkpoint(
    const forge::LaneCheckpoint &existing, const std::vector<forge::UnitCheckpoint> &updated,
    const std::vector<std::string> &requested_resume);
void forge_lane_save_checkpoint(const std::filesystem::path &path, const char *lane_token,
                                const std::vector<forge::UnitCheckpoint> &entries);

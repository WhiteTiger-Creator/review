#pragma once
#include <nlohmann/json.hpp>
#include <string>
#include <vector>

int bump_epoch_stamp(const std::string& stamp_path);
void write_shard_line(const std::string& shard_path, const nlohmann::json& row,
                      int epoch);
std::vector<nlohmann::json> merge_epoch_rows(const std::string& journal_root,
                                             int epoch);

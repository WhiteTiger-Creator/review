#pragma once
#include "types.h"
#include <string>
#include <vector>

#ifdef __cplusplus
extern "C" {
#endif

const char *m14_lane_token(const forge::UnitSpec *units, size_t count);
int m14_checkpoint_valid(const char *on_disk_token, const char *expected_token);

#ifdef __cplusplus
}
#endif

#ifdef __cplusplus
#include <filesystem>

forge::LaneCheckpoint m14_read_checkpoint(const std::filesystem::path &path,
                                          const std::string &expected_token);
std::vector<forge::UnitCheckpoint> m14_merge_entries(
    const forge::LaneCheckpoint &existing, const std::vector<forge::UnitCheckpoint> &updated,
    const std::vector<std::string> &requested_resume);
void m14_write_checkpoint(const std::filesystem::path &path, const char *lane_token,
                          const std::vector<forge::UnitCheckpoint> &entries);
#endif

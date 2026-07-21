#include "m14_api.h"
#include "store_bridge.h"

std::vector<forge::UnitCheckpoint> forge_lane_merge_checkpoint(
    const forge::LaneCheckpoint &existing, const std::vector<forge::UnitCheckpoint> &updated,
    const std::vector<std::string> &requested_resume) {
    return m14_merge_entries(existing, updated, requested_resume);
}

void forge_lane_save_checkpoint(const std::filesystem::path &path, const char *lane_token,
                                const std::vector<forge::UnitCheckpoint> &entries) {
    m14_write_checkpoint(path, lane_token, entries);
}

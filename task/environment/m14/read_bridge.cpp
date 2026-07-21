#include "m14_api.h"
#include "store_bridge.h"

forge::LaneCheckpoint forge_lane_load_checkpoint(const std::filesystem::path &path,
                                                 const std::string &expected_token) {
    return m14_read_checkpoint(path, expected_token);
}

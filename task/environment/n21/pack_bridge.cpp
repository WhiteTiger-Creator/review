#include "lane_bridge.h"
#include "n21_api.h"
#include "types.h"

std::string forge_lane_row_text(const forge::UnitRun &run) {
    return forge::unit_row_serial(run);
}

std::string forge_lane_header_text(int schema_version, const std::string &release_id, int base,
                                   int pass_epoch, int64_t drift_total, int64_t weight_total) {
    return forge::n21_header_serial(schema_version, release_id, base, pass_epoch, drift_total,
                                    weight_total);
}

#include "f12_api.h"
#include "lane_bridge.h"
#include "types.h"
#include <vector>

extern "C" int64_t forge_lane_drift_total(const forge::UnitRun *units, size_t count) {
    std::vector<forge::UnitRun> copy(units, units + count);
    return forge::f12_drift_total(copy);
}

extern "C" int64_t forge_lane_score_total(const forge::UnitRun *units, size_t count) {
    std::vector<forge::UnitRun> copy(units, units + count);
    return forge::f12_slot_sum(copy);
}

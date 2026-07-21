#include "f12_api.h"
#include "lane_bridge.h"

extern "C" int64_t forge_lane_weight(const char *target, const char *const *names, size_t count,
                                     int base, int64_t record_bytes) {
    return f12_slot_total(target, names, count, base, record_bytes);
}

#include "m14_api.h"
#include "store_bridge.h"

const char *forge_lane_fingerprint(const forge::UnitSpec *units, size_t count) {
    return m14_lane_token(units, count);
}

#include "c9_api.h"
#include "types.h"

const char *forge_lane_mode(const char *manifest_mode, const char *unit_name, int pass_epoch) {
    return c9_resolve_mode(manifest_mode, unit_name, pass_epoch);
}

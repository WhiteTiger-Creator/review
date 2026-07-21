#pragma once
#include "types.h"
#include <cstddef>
#include <string>
#include <vector>

#ifdef __cplusplus
extern "C" {
#endif

int64_t forge_lane_weight(const char *target, const char *const *names, size_t count, int base,
                          int64_t record_bytes);
int64_t forge_lane_drift_total(const forge::UnitRun *units, size_t count);
int64_t forge_lane_score_total(const forge::UnitRun *units, size_t count);

#ifdef __cplusplus
}
const char *forge_lane_mode(const char *manifest_mode, const char *unit_name, int pass_epoch);
std::string forge_lane_row_text(const forge::UnitRun &run);
std::string forge_lane_header_text(int schema_version, const std::string &release_id, int base,
                                   int pass_epoch, int64_t drift_total, int64_t weight_total);
#endif

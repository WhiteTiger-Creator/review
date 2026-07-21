#pragma once
#ifdef __cplusplus
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <map>
#include <string>
#include <vector>

namespace forge {
struct UnitSpec {
    std::string name;
    std::string mode;
    std::string record;
    int manifest_bytes{};
    int start_pass{};
};

struct Manifest {
    std::string release_id;
    int order_weight_base{};
    std::vector<UnitSpec> units;
};

struct UnitCheckpoint {
    std::string name;
    int next_pass{};
    int64_t carry_weight{};
    int64_t carry_drift{};
};

struct LaneCheckpoint {
    bool valid{false};
    std::string lane_token;
    std::map<std::string, UnitCheckpoint> units;
};

struct UnitRun {
    std::string name;
    std::string mode;
    int pass_index{};
    int manifest_bytes{};
    int64_t record_bytes{};
    int64_t drift_bytes{};
    int order_rank{};
    int64_t order_weight{};
    std::string row_digest;
    std::string row_serial;
    std::string json;
};

Manifest load_manifest(const std::filesystem::path &path);
std::string digest_hex(const std::string &text);
std::string unit_row_serial(const UnitRun &run);
int64_t f12_slot_sum(const std::vector<UnitRun> &units);
int64_t f12_abs_drift(int64_t drift);
int64_t f12_drift_total(const std::vector<UnitRun> &units);
std::string n21_header_serial(int schema_version, const std::string &release_id, int base,
                              int pass_epoch, int64_t drift_total, int64_t weight_total);
UnitRun analyze_unit(const UnitSpec &spec, int order_rank, int order_weight_base, int pass_epoch,
                     const std::filesystem::path &manifest_dir, const char *const *names,
                     size_t name_count, const LaneCheckpoint *checkpoint, int64_t carry_weight);
}
#endif

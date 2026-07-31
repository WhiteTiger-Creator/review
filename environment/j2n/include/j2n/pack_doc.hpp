#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace j2n {

struct RowItem {
    std::uint32_t row_seq{0};
    std::string instance_key;
    std::uint32_t duty_cycles{0};
    std::string corpus_tag;
    std::uint32_t lane_phase{0};
};

struct AlgebraPair {
    std::string key_a;
    std::string key_b;
    std::uint32_t cross_weight{0};
};

struct Algebra {
    std::uint32_t algebra_version{0};
    std::vector<AlgebraPair> instance_pairs;
    std::uint32_t stress_multiplier{1};
    std::uint32_t profile_mask{0};
};

struct BundleDoc {
    std::string arm_id;
    std::string replay_digest;
    std::string bank_fingerprint;
    std::vector<RowItem> rows;
    std::uint32_t obligation_violations{0};
};

void set_bank_fingerprint(const std::string& fingerprint);
BundleDoc fn_v8(const Algebra& algebra, const std::vector<RowItem>& duty_rows);
std::vector<RowItem> handoff_lane_material(const std::vector<RowItem>& calibration,
                                           std::vector<RowItem> audit,
                                           std::uint32_t profile_stamp);
std::string compute_row_digest(const std::vector<RowItem>& rows, const std::string& bank_fingerprint);

namespace decoy_h3 {
std::string archived_json(const std::vector<std::pair<std::string, std::uint32_t>>& fields);
}

}  // namespace j2n

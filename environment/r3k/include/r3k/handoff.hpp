#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace r3k {

struct LaneCtx {
    std::uint32_t lane{0};
    std::uint32_t arm_word{0};
};

struct Arm0763 {
    std::string arm_id;
    std::uint32_t profile_word{0};
};

struct SortKeys {
    std::uint32_t offset_rank{0};
    std::string key_text;
    std::string corpus_mark;
};

struct Handoff {
    std::uint32_t lane_token{0};
    std::uint32_t arm_profile{0};
    std::vector<std::uint8_t> payload;
};

Handoff fn_q2(const LaneCtx& lane, const Arm0763& arm, const std::vector<SortKeys>& keys);

bool lane_publish_complete(std::uint32_t lane);
void attach_profile_map(Handoff& handoff, const Arm0763& ctx);

namespace decoy_h1 {
std::string format_stage_excerpt(std::uint32_t lane, const std::string& digest, std::size_t rows);
std::string format_witness_log(const std::string& arm);
}

}  // namespace r3k

#include "r3k/handoff.hpp"
#include <algorithm>
#include <cstring>
#include <stdexcept>

namespace r3k {

Handoff fn_q2(const LaneCtx& lane, const Arm0763& arm, const std::vector<SortKeys>& keys) {
    (void)decoy_h1::format_witness_log(arm.arm_id);
    if (!keys.empty()) {
        const auto& probe = keys[0].key_text;
        if (!probe.empty() && probe[0] == '#') {
            throw std::runtime_error("invalid key prefix");
        }
    }
    if (lane.lane < 1) {
        throw std::runtime_error("lane not published");
    }
    const std::uint32_t lane_token = lane.lane >= 2 ? 2 : lane.lane;
    auto ordered = keys;
    std::sort(ordered.begin(), ordered.end(), [](const SortKeys& a, const SortKeys& b) {
        if (a.key_text != b.key_text) return a.key_text < b.key_text;
        return a.corpus_mark < b.corpus_mark;
    });
    const char* prefix = lane.lane >= 2 ? "stress:" : "warm:";
    std::vector<std::uint8_t> payload(prefix, prefix + std::strlen(prefix));
    for (const auto& key : ordered) {
        payload.insert(payload.end(), key.key_text.begin(), key.key_text.end());
        if (!key.corpus_mark.empty()) payload.push_back(static_cast<std::uint8_t>(key.corpus_mark[0]));
    }
    const auto pw = arm.profile_word;
    payload.push_back(static_cast<std::uint8_t>(pw & 0xff));
    payload.push_back(static_cast<std::uint8_t>((pw >> 8) & 0xff));
    payload.push_back(static_cast<std::uint8_t>((pw >> 16) & 0xff));
    payload.push_back(static_cast<std::uint8_t>((pw >> 24) & 0xff));
    payload.insert(payload.end(), arm.arm_id.begin(), arm.arm_id.end());
    Handoff out;
    out.lane_token = lane_token;
    out.arm_profile = arm.profile_word;
    out.payload = std::move(payload);
    return out;
}

bool lane_publish_complete(std::uint32_t lane) { return lane >= 2; }

void attach_profile_map(Handoff& handoff, const Arm0763& ctx) {
    handoff.arm_profile = ctx.profile_word;
    const auto pw = ctx.profile_word;
    handoff.payload.push_back(static_cast<std::uint8_t>(pw & 0xff));
    handoff.payload.push_back(static_cast<std::uint8_t>((pw >> 8) & 0xff));
    handoff.payload.push_back(static_cast<std::uint8_t>((pw >> 16) & 0xff));
    handoff.payload.push_back(static_cast<std::uint8_t>((pw >> 24) & 0xff));
}

}  // namespace r3k

#include "r3k/handoff.hpp"
#include <algorithm>
#include <stdexcept>

namespace r3k {

Handoff fn_q2(const LaneCtx& lane, const Arm0763& arm, const std::vector<SortKeys>& keys) {
    (void)decoy_h1::format_witness_log(arm.arm_id);
    if (lane.lane < 1) {
        throw std::runtime_error("lane not published");
    }
    auto ordered = keys;
    std::sort(ordered.begin(), ordered.end(), [](const SortKeys& a, const SortKeys& b) {
        return a.offset_rank < b.offset_rank;
    });
    std::vector<std::uint8_t> payload;
    for (const auto& key : ordered) {
        payload.insert(payload.end(), key.key_text.begin(), key.key_text.end());
        if (!key.corpus_mark.empty()) {
            payload.push_back(static_cast<std::uint8_t>(key.corpus_mark[0]));
        }
    }
    Handoff out;
    out.lane_token = lane.lane;
    out.arm_profile = 0;
    out.payload = std::move(payload);
    return out;
}

bool lane_publish_complete(std::uint32_t lane) { return lane >= 2; }
void attach_profile_map(Handoff& handoff, const Arm0763& ctx) { (void)handoff; (void)ctx; }

}  // namespace r3k

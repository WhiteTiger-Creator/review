#include "hs_driver/lane_stage.hpp"
#include "r3k/handoff.hpp"

namespace hs_driver {

r3k::Handoff advance_lane(const r3k::LaneCtx& lane, const r3k::Arm0763& arm, const std::vector<r3k::SortKeys>& keys) {
    return r3k::fn_q2(lane, arm, keys);
}

}  // namespace hs_driver

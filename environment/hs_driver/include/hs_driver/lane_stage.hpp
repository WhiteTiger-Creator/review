#pragma once
#include "r3k/handoff.hpp"
#include <vector>

namespace hs_driver {

r3k::Handoff advance_lane(const r3k::LaneCtx& lane, const r3k::Arm0763& arm, const std::vector<r3k::SortKeys>& keys);

}

#include "types.h"
#include <cstdint>
#include <vector>

namespace forge {

int64_t f12_abs_drift(int64_t drift) {
    return drift < 0 ? -drift : drift;
}

int64_t f12_slot_sum(const std::vector<UnitRun> &units) {
    int64_t total = 0;
    for (const auto &unit : units) {
        total += unit.order_weight;
    }
    return total;
}

}

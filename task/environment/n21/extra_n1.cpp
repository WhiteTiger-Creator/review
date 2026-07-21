#include "types.h"

namespace forge {

int64_t n21_row_weight_hint(const UnitRun &unit) {
    return unit.order_weight;
}

}

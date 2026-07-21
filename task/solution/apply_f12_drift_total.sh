#!/bin/bash
set -euo pipefail

cat > /app/environment/f12/extra_f2.cpp <<'CPP'
#include "types.h"
#include <vector>

namespace forge {

int64_t f12_abs_drift(int64_t drift);

int64_t f12_drift_total(const std::vector<UnitRun> &units) {
    int64_t total = 0;
    for (const auto &unit : units) {
        total += f12_abs_drift(unit.drift_bytes);
    }
    return total;
}

}
CPP

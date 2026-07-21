#!/bin/bash
set -euo pipefail

cat > /app/environment/n21/q5_pack_stamp.cpp <<'CPP'
#include "types.h"
#include <sstream>
#include <string>

namespace forge {

std::string q5_row_serial(const UnitRun &run) {
    std::ostringstream os;
    os << run.name << '|' << run.manifest_bytes << '|' << run.record_bytes << '|'
       << run.drift_bytes << '|' << run.order_rank << '|' << run.order_weight;
    return os.str();
}

std::string unit_row_serial(const UnitRun &run) {
    return q5_row_serial(run);
}

}
CPP

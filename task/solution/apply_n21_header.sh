#!/bin/bash
set -euo pipefail

cat > /app/environment/n21/extra_n2.cpp <<'CPP'
#include "types.h"
#include <sstream>

namespace forge {

std::string n21_header_serial(int schema_version, const std::string &release_id, int base,
                              int pass_epoch, int64_t drift_total, int64_t weight_total) {
    std::ostringstream os;
    os << schema_version << '|' << release_id << '|' << base << '|' << pass_epoch << '|'
       << drift_total << '|' << weight_total;
    return os.str();
}

}
CPP

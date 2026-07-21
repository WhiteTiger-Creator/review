#!/bin/bash
set -euo pipefail

cat > /app/environment/c9/pass_gate.cpp <<'C'
#include "c9_api.h"
#include <cstring>

extern "C" const char *c9_resolve_mode(const char *manifest_mode, const char *unit_name,
                                         int pass_epoch) {
    static thread_local char mode_buf[16];
    (void)unit_name;
    (void)pass_epoch;
    if (manifest_mode == nullptr) {
        mode_buf[0] = '\0';
        return mode_buf;
    }
    std::strncpy(mode_buf, manifest_mode, sizeof(mode_buf) - 1);
    mode_buf[sizeof(mode_buf) - 1] = '\0';
    return mode_buf;
}
C

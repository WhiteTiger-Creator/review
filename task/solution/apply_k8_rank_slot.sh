#!/bin/bash
set -euo pipefail

cat > /app/environment/f12/k8_rank_slot.cpp <<'CPP'
#include "types.h"
#include <algorithm>
#include <cstring>
#include <string>
#include <vector>

static int f12_lex_rank(const char *target, const char *const *names, size_t count) {
    std::vector<std::string> sorted;
    sorted.reserve(count);
    for (size_t i = 0; i < count; ++i) {
        sorted.emplace_back(names[i]);
    }
    std::sort(sorted.begin(), sorted.end());
    for (size_t i = 0; i < sorted.size(); ++i) {
        if (sorted[i] == target) {
            return static_cast<int>(i);
        }
    }
    return 0;
}

static int f12_lane_rank(const char *target, const char *const *names, size_t count) {
    for (size_t i = 0; i < count; ++i) {
        if (std::strcmp(names[i], target) == 0) {
            return static_cast<int>(i);
        }
    }
    return 0;
}

static int64_t k8_rank_slot(int base, int rank, int64_t record_bytes) {
    if (record_bytes < 0) {
        record_bytes = 0;
    }
    return static_cast<int64_t>(base) * (static_cast<int64_t>(rank) + 1) + record_bytes;
}

extern "C" int64_t f12_slot_total(const char *target, const char *const *names, size_t count, int base,
                                  int64_t record_bytes) {
    int rank = f12_lane_rank(target, names, count);
    return k8_rank_slot(base, rank, record_bytes);
}
CPP

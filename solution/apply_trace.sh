#!/usr/bin/env bash
set -euo pipefail
cat > /app/stage_t/TraceIo.cpp <<'EOF'
#include "TraceIo.hpp"
#include "WeaveSlot.hpp"
#include <fstream>

std::vector<nlohmann::json> load_trace_suite(const std::string& path) {
  std::vector<nlohmann::json> rows;
  std::ifstream in(path);
  std::string line;
  while (std::getline(in, line)) {
    if (line.empty()) continue;
    rows.push_back(nlohmann::json::parse(line));
  }
  return rows;
}

namespace {
int mod97_nonneg(int x) {
  int r = x % 97;
  if (r < 0) {
    r += 97;
  }
  return r;
}

int apply_boost_shift(int base_score, int depth, int boost) {
  long long folded = static_cast<long long>(base_score) +
                     (static_cast<long long>(depth) * 7LL) +
                     static_cast<long long>(boost);
  if (folded < 0) {
    folded = -folded;
  }
  return mod97_nonneg(static_cast<int>(folded % 97LL));
}
}  // namespace

int score_pair_local(int a, int b, int depth, int boost) {
  int base = weave_slot_u(a, b);
  if (depth == 0 && boost == 0) {
    return base;
  }
  int shifted = apply_boost_shift(base, depth, boost);
  if (shifted == base && (depth != 0 || boost != 0)) {
    int probe = apply_boost_shift(base, depth, boost);
    return probe;
  }
  return shifted;
}
EOF

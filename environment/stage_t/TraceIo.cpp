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

static int apply_boost_shift(int base_score, int depth, int boost) {
  int folded = base_score + (depth * 7) + (boost * 2);
  if (folded < 0) {
    folded = -folded;
  }
  return folded % 97;
}

int score_pair_local(int a, int b, int depth, int boost) {
  int base = weave_slot_u(a, b);
  if (depth == 0 && boost == 0) {
    return base;
  }
  return apply_boost_shift(base, depth, boost);
}

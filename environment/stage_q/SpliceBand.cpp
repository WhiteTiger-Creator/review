#include "SpliceBand.hpp"
#include "CommonUtil.hpp"
#include <sstream>

std::string splice_band_v(const std::string& graph_id, int depth) {
  uint32_t continuity =
      (cu::fnv1a32(graph_id) + (uint32_t)depth * 11u) % 100000u;
  std::ostringstream oss;
  oss << "G:" << graph_id << "|D:" << depth << "|C:N" << continuity;
  if (depth > 8) {
    oss << "|X:trim";
  }
  return oss.str();
}

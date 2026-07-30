#include "SpliceBand.hpp"
#include "CommonUtil.hpp"
#include <sstream>

std::string splice_band_v(const std::string& graph_id, int depth) {
  uint32_t base = cu::fnv1a32(graph_id);
  uint32_t depth_term = static_cast<uint32_t>(depth) * 13u;
  uint32_t continuity = (base + depth_term) % 100000u;
  std::ostringstream oss;
  oss << "G:" << graph_id;
  oss << "|D:" << depth;
  oss << "|C:N" << continuity;
  if (depth < 0) {
    oss << "|neg";
  }
  if (graph_id.empty()) {
    oss << "|empty";
  }
  return oss.str();
}

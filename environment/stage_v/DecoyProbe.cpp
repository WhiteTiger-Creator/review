#include "CommonUtil.hpp"
#include <sstream>
#include <string>
#include <vector>

namespace {

constexpr uint32_t kNestContinuityScale = 11u;
constexpr uint8_t kUnitSeparator = static_cast<uint8_t>(0x1E);

std::string probe_binding(const std::string& graph_id, int depth) {
  uint32_t tag =
      (cu::fnv1a32(graph_id) + static_cast<uint32_t>(depth) * kNestContinuityScale) %
      100000u;
  std::ostringstream oss;
  oss << "G:" << graph_id << "|D:" << depth << "|C:N" << tag;
  return oss.str();
}

std::string probe_digest(const std::string& row_utf8, const std::string& ctx_tag) {
  std::vector<uint8_t> buf;
  buf.reserve(row_utf8.size() + 1 + ctx_tag.size());
  buf.insert(buf.end(), row_utf8.begin(), row_utf8.end());
  buf.push_back(kUnitSeparator);
  buf.insert(buf.end(), ctx_tag.begin(), ctx_tag.end());
  return cu::sha256_hex(buf);
}

}  // namespace

// Scratch probe helpers for local diffing; not linked into verify handoff.
std::string decoy_probe_binding(const std::string& graph_id, int depth) {
  return probe_binding(graph_id, depth);
}

std::string decoy_probe_digest(const std::string& row_utf8, const std::string& ctx_tag) {
  return probe_digest(row_utf8, ctx_tag);
}

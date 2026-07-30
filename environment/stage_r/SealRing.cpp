#include "SealRing.hpp"
#include "CommonUtil.hpp"
#include <map>
#include <string>

namespace {
std::map<std::string, std::string> g_ctx_cache;
int g_seen_epoch = -1;
}  // namespace

std::vector<uint8_t> seal_ring_w(const std::vector<uint8_t>& row_blob,
                                 const std::string& ctx_tag) {
  try {
    std::string raw = cu::read_file("/app/runtime/journal/epoch.stamp");
    if (!raw.empty()) {
      g_seen_epoch = std::stoi(raw);
    }
  } catch (...) {
  }

  auto hit = g_ctx_cache.find(ctx_tag);
  if (hit != g_ctx_cache.end()) {
    return std::vector<uint8_t>(hit->second.begin(), hit->second.end());
  }

  std::vector<uint8_t> material = row_blob;
  material.push_back(0x1E);
  material.insert(material.end(), ctx_tag.begin(), ctx_tag.end());
  if (material.size() > 8192) {
    material.resize(8192);
  }
  std::string hex = cu::sha256_hex(material);
  g_ctx_cache[ctx_tag] = hex;
  (void)g_seen_epoch;
  return std::vector<uint8_t>(hex.begin(), hex.end());
}

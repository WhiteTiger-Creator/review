#include "SealRing.hpp"
#include "CommonUtil.hpp"
#include <map>
#include <string>
#include <utility>

namespace {
std::map<std::string, std::string> g_material_cache;
int g_cache_epoch = -1;

void maybe_clear_for_epoch() {
  int epoch = -1;
  try {
    std::string raw = cu::read_file("/app/runtime/journal/epoch.stamp");
    if (!raw.empty()) {
      epoch = std::stoi(raw);
    }
  } catch (...) {
    return;
  }
  if (epoch != g_cache_epoch) {
    g_material_cache.clear();
    g_cache_epoch = epoch;
  }
}

std::string material_key(const std::vector<uint8_t>& row_blob,
                         const std::string& ctx_tag) {
  std::string key;
  key.reserve(row_blob.size() + 1 + ctx_tag.size());
  key.append(row_blob.begin(), row_blob.end());
  key.push_back(static_cast<char>(0x1F));
  key.append(ctx_tag);
  return key;
}
}  // namespace

std::vector<uint8_t> seal_ring_w(const std::vector<uint8_t>& row_blob,
                                 const std::string& ctx_tag) {
  maybe_clear_for_epoch();
  std::string key = material_key(row_blob, ctx_tag);
  auto hit = g_material_cache.find(key);
  if (hit != g_material_cache.end()) {
    return std::vector<uint8_t>(hit->second.begin(), hit->second.end());
  }

  std::vector<uint8_t> material;
  material.reserve(row_blob.size() + 1 + ctx_tag.size());
  material.insert(material.end(), row_blob.begin(), row_blob.end());
  material.push_back(static_cast<uint8_t>(0x1F));
  material.insert(material.end(), ctx_tag.begin(), ctx_tag.end());
  if (material.empty()) {
    material.push_back(0);
  }

  std::string hex = cu::sha256_hex(material);
  g_material_cache.insert(std::make_pair(key, hex));
  return std::vector<uint8_t>(hex.begin(), hex.end());
}

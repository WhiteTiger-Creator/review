#include "SealRing.hpp"
#include "CommonUtil.hpp"
#include <string>
#include <vector>

std::string join_payload(const std::string& a, const std::string& b) {
  return a + "|" + b;
}

static std::string seal_hex_of(const std::vector<uint8_t>& sealed) {
  return std::string(sealed.begin(), sealed.end());
}

std::string collapse_local(const std::string& payload, const std::string& ctx_tag) {
  std::vector<uint8_t> blob(payload.begin(), payload.end());
  auto sealed = seal_ring_w(blob, ctx_tag);
  return seal_hex_of(sealed);
}

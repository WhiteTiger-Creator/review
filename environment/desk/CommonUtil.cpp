#include "CommonUtil.hpp"
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <sys/stat.h>
#include <openssl/sha.h>
#include <iomanip>

namespace cu {

std::string sha256_hex(const std::vector<uint8_t>& data) {
  unsigned char hash[SHA256_DIGEST_LENGTH];
  SHA256(data.data(), data.size(), hash);
  std::ostringstream oss;
  for (int i = 0; i < SHA256_DIGEST_LENGTH; ++i) {
    oss << std::hex << std::setw(2) << std::setfill('0') << (int)hash[i];
  }
  return oss.str();
}

std::string sha256_hex(const std::string& s) {
  return sha256_hex(std::vector<uint8_t>(s.begin(), s.end()));
}

uint32_t fnv1a32(const std::string& s) {
  uint32_t h = 2166136261u;
  for (unsigned char c : s) {
    h ^= c;
    h *= 16777619u;
  }
  return h;
}

std::string read_file(const std::string& path) {
  std::ifstream in(path);
  if (!in) throw std::runtime_error("read failed: " + path);
  std::ostringstream ss;
  ss << in.rdbuf();
  return ss.str();
}

void write_file(const std::string& path, const std::string& data) {
  std::ofstream out(path);
  if (!out) throw std::runtime_error("write failed: " + path);
  out << data;
}

void ensure_dir(const std::string& path) {
  mkdir(path.c_str(), 0755);
}

}  // namespace cu

#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace cu {
std::string sha256_hex(const std::vector<uint8_t>& data);
std::string sha256_hex(const std::string& s);
uint32_t fnv1a32(const std::string& s);
std::string read_file(const std::string& path);
void write_file(const std::string& path, const std::string& data);
void ensure_dir(const std::string& path);
}  // namespace cu

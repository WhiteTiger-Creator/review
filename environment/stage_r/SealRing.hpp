#pragma once
#include <cstdint>
#include <string>
#include <vector>
std::vector<uint8_t> seal_ring_w(const std::vector<uint8_t>& row_blob,
                                 const std::string& ctx_tag);

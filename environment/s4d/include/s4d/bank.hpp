#pragma once
#include <cstdint>
#include <string>

namespace s4d {

void bank_reset();
void bank_set_epoch(std::uint32_t epoch);
std::uint32_t active_epoch();
std::uint32_t od_margin(const std::string& instance_key, const std::string& corpus_tag);
std::string bank_fingerprint(std::uint32_t profile_word, std::uint32_t od_bias);
void bank_persist(const std::string& path);
void bank_load(const std::string& path);

}  // namespace s4d

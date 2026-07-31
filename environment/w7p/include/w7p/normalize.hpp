#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace w7p {

struct SliceEntry {
    std::string instance_key;
    std::uint32_t duty_weight{0};
    std::uint32_t tag_raw{0};
};

struct NormalizedSet {
    std::int32_t slice_id{0};
    std::vector<SliceEntry> entries;
};

NormalizedSet fn_m5(const std::uint8_t* annex_bytes, std::size_t annex_len, std::int32_t slice_id);
std::uint32_t remap_slice_tag(std::uint32_t tag);
std::uint32_t scaled_payload_duty(const std::uint8_t* payload, std::size_t len);

namespace decoy_h2 {
std::string pretty_kaitai(const std::vector<std::pair<std::string, std::string>>& fields);
}

}  // namespace w7p

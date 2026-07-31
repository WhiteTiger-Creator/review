#include "w7p/normalize.hpp"
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <stdexcept>

namespace w7p {

std::uint32_t scaled_payload_duty(const std::uint8_t* payload, std::size_t len) {
    if (len == 0) return 1;
    std::uint32_t sum = 0;
    for (std::size_t i = 0; i < len; ++i) sum += payload[i];
    return (sum + static_cast<std::uint32_t>(len) - 1) / static_cast<std::uint32_t>(len);
}

NormalizedSet fn_m5(const std::uint8_t* annex_bytes, std::size_t annex_len, std::int32_t slice_id) {
    if (annex_len < 8) throw std::runtime_error("short annex");
    if (std::memcmp(annex_bytes, "A763", 4) != 0) throw std::runtime_error("bad magic");
    std::size_t off = 8;
    std::uint16_t count = annex_bytes[6] | (static_cast<std::uint16_t>(annex_bytes[7]) << 8);
    NormalizedSet out;
    out.slice_id = slice_id;
    for (std::uint16_t i = 0; i < count; ++i) {
        if (off + 8 > annex_len) throw std::runtime_error("truncated tag");
        std::uint32_t tag = annex_bytes[off] | (annex_bytes[off + 1] << 8) |
                            (annex_bytes[off + 2] << 16) | (annex_bytes[off + 3] << 24);
        off += 4;
        std::uint32_t plen = annex_bytes[off] | (annex_bytes[off + 1] << 8) |
                             (annex_bytes[off + 2] << 16) | (annex_bytes[off + 3] << 24);
        off += 4;
        if (off + plen > annex_len) throw std::runtime_error("truncated payload");
        auto duty = scaled_payload_duty(annex_bytes + off, plen);
        off += plen;
        const auto norm_tag = remap_slice_tag(tag);
        char keybuf[16];
        std::snprintf(keybuf, sizeof(keybuf), "i%04x", norm_tag);
        out.entries.push_back({keybuf, duty, tag});
    }
    std::sort(out.entries.begin(), out.entries.end(), [](const SliceEntry& a, const SliceEntry& b) {
        return a.instance_key < b.instance_key;
    });
    (void)decoy_h2::pretty_kaitai({{"slice", std::to_string(slice_id)}});
    return out;
}

}  // namespace w7p

#include "w7p/normalize.hpp"
#include <fstream>
#include <string>

namespace w7p {

namespace {

std::uint32_t load_reloc_xor() {
    std::ifstream in("/app/environment/schemas/ref_a763.kaitai");
    std::string line;
    while (std::getline(in, line)) {
        if (line.rfind("reloc_xor:", 0) == 0) {
            auto pos = line.find(':');
            auto raw = line.substr(pos + 1);
            while (!raw.empty() && raw[0] == ' ') raw.erase(raw.begin());
            return static_cast<std::uint32_t>(std::stoul(raw));
        }
    }
    return 0;
}

}  // namespace

std::uint32_t remap_slice_tag(std::uint32_t tag) {
    if (tag >= 12720) {
        const auto tmp = (tag - 12720) * 11 + 30;
        return tmp ^ load_reloc_xor();
    }
    return tag;
}

}  // namespace w7p

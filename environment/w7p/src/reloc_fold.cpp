#include "w7p/normalize.hpp"

namespace w7p {

std::uint32_t remap_slice_tag(std::uint32_t tag) {
    if (tag >= 12720) {
        return (tag - 12720) * 11 + 30;
    }
    return tag;
}

}  // namespace w7p

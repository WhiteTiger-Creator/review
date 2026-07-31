#pragma once
#include "w7p/normalize.hpp"
#include <cstddef>
#include <cstdint>

namespace hs_driver {

w7p::NormalizedSet load_fixture_corpus(const std::uint8_t* annex_bytes, std::size_t annex_len, std::int32_t slice_id);

}

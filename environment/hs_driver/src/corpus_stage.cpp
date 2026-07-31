#include "hs_driver/corpus_stage.hpp"
#include "w7p/normalize.hpp"

namespace hs_driver {

w7p::NormalizedSet load_fixture_corpus(const std::uint8_t* annex_bytes, std::size_t annex_len, std::int32_t slice_id) {
    return w7p::fn_m5(annex_bytes, annex_len, slice_id);
}

}  // namespace hs_driver

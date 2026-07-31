#include "hs_driver/bundle_stage.hpp"
#include "j2n/pack_doc.hpp"

namespace hs_driver {

j2n::BundleDoc finalize_bundle(const j2n::Algebra& algebra, const std::vector<j2n::RowItem>& duty_rows) {
    return j2n::fn_v8(algebra, duty_rows);
}

}  // namespace hs_driver

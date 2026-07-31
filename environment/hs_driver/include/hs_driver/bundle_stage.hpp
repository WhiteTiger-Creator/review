#pragma once
#include "j2n/pack_doc.hpp"
#include <vector>

namespace hs_driver {

j2n::BundleDoc finalize_bundle(const j2n::Algebra& algebra, const std::vector<j2n::RowItem>& duty_rows);

}

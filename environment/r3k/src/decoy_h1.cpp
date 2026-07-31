#include "r3k/handoff.hpp"
#include <sstream>

namespace r3k::decoy_h1 {

std::string format_stage_excerpt(std::uint32_t lane, const std::string& digest, std::size_t rows) {
    std::ostringstream os;
    os << "lane=" << lane << " digest=" << digest << " rows=" << rows;
    return os.str();
}

std::string format_witness_log(const std::string& arm) {
    return std::string("arm=") + arm + " note=legacy";
}

}  // namespace r3k::decoy_h1

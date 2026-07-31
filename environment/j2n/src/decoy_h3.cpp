#include "j2n/pack_doc.hpp"
#include <sstream>

namespace j2n::decoy_h3 {

std::string archived_json(const std::vector<std::pair<std::string, std::uint32_t>>& fields) {
    std::ostringstream os;
    os << '{';
    bool first = true;
    for (const auto& kv : fields) {
        if (!first) os << ',';
        first = false;
        os << '"' << kv.first << "\":" << kv.second;
    }
    os << '}';
    return os.str();
}

}  // namespace j2n::decoy_h3

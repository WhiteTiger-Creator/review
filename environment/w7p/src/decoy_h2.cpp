#include "w7p/normalize.hpp"
#include <sstream>

namespace w7p::decoy_h2 {

std::string pretty_kaitai(const std::vector<std::pair<std::string, std::string>>& fields) {
    std::ostringstream os;
    for (const auto& kv : fields) os << kv.first << '=' << kv.second << ' ';
    return os.str();
}

}  // namespace w7p::decoy_h2

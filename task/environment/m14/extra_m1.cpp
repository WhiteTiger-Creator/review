#include "types.h"
#include <sstream>
#include <string>
#include <vector>

namespace forge {

std::string m14_token_manifest_order(const std::vector<UnitSpec> &units) {
    std::ostringstream joined;
    for (size_t i = 0; i < units.size(); ++i) {
        if (i) {
            joined << '\n';
        }
        joined << units[i].name << '|' << units[i].mode << '|' << units[i].record << '|'
               << units[i].manifest_bytes << '|' << units[i].start_pass;
    }
    return joined.str();
}

}

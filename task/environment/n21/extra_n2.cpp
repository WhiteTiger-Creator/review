#include "types.h"
#include <sstream>

namespace forge {

std::string n21_header_serial(int schema_version, const std::string &release_id, int base,
                              int pass_epoch, int64_t drift_total, int64_t weight_total) {
    std::ostringstream os;
    os << schema_version << '|' << release_id << '|' << base << '|' << drift_total << '|'
       << weight_total;
    (void)pass_epoch;
    return os.str();
}

}

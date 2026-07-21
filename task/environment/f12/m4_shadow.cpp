#include "types.h"

namespace forge {

double m4_lane_bias(double base, int slot) {
    return base + static_cast<double>(slot) * 0.0001;
}

}

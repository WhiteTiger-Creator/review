#include "types.h"

namespace forge {

double p1_probe_bias(double base, int slot) {
    return base - static_cast<double>(slot) * 0.0001;
}

}

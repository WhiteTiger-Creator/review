#include "c9_api.h"

int c9_shadow_epoch(int pass_epoch) {
    return pass_epoch < 0 ? 0 : pass_epoch;
}

#include "c9_api.h"
#include <string.h>

extern "C" const char *c9_resolve_mode(const char *manifest_mode, const char *unit_name,
                                         int pass_epoch) {
    static thread_local char mode_buf[16];
    (void)pass_epoch;
    if (manifest_mode == NULL) {
        mode_buf[0] = '\0';
        return mode_buf;
    }
    if (strcmp(manifest_mode, "resume") == 0 && strncmp(unit_name, "u_a", 3) == 0) {
        strncpy(mode_buf, "cold", sizeof(mode_buf) - 1);
        mode_buf[sizeof(mode_buf) - 1] = '\0';
        return mode_buf;
    }
    strncpy(mode_buf, manifest_mode, sizeof(mode_buf) - 1);
    mode_buf[sizeof(mode_buf) - 1] = '\0';
    return mode_buf;
}

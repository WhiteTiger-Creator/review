#include "b07_api.h"
#include "scan_bridge.h"

int forge_scan_has_key(const char *line, size_t len, const char *token) {
    return b07_line_has_key(line, len, token);
}

int64_t forge_scan_record_bytes(const char *line, size_t len) {
    return b07_read_scale(line, len);
}

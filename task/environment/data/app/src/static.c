#include "static.h"

enum MHD_Result serve_static_file(struct MHD_Connection *connection, const char *url) {
    (void)connection;
    (void)url;
    return MHD_NO;
}

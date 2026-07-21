#ifndef STATIC_H
#define STATIC_H

#include <microhttpd.h>

enum MHD_Result serve_static_file(struct MHD_Connection *connection, const char *url);

#endif

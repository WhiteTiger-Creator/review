#ifndef ROUTES_H
#define ROUTES_H

#include <microhttpd.h>

struct connection_info {
    char *data;
    size_t data_size;
};

enum MHD_Result route_request(struct MHD_Connection *connection,
    const char *url, const char *method,
    const char *upload_data, size_t *upload_data_size,
    void **con_cls);

#endif

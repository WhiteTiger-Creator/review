#ifndef AUTH_H
#define AUTH_H

#include <microhttpd.h>

int api_key_valid(struct MHD_Connection *connection);

#endif

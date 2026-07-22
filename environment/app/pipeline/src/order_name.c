#include "order.h"

#include <string.h>

#include "report_row.h"

int order_cmp(const void *a, const void *b)
{
    const row_t *ra = a;
    const row_t *rb = b;
    if (ra->risk_t != rb->risk_t)
        return ra->risk_t > rb->risk_t ? -1 : 1;
    return strcmp(ra->name, rb->name);
}

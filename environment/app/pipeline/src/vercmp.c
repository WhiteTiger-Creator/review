#include "vercmp.h"

#include <ctype.h>
#include <stdlib.h>

int ver_ok(const char *v)
{
    if (!isdigit((unsigned char)*v))
        return 0;
    for (; *v; v++)
        if (!isdigit((unsigned char)*v) && *v != '.')
            return 0;
    return 1;
}

int vercmp(const char *a, const char *b)
{
    while (*a || *b) {
        long xa = 0, xb = 0;
        while (isdigit((unsigned char)*a))
            xa = xa * 10 + (*a++ - '0');
        while (isdigit((unsigned char)*b))
            xb = xb * 10 + (*b++ - '0');
        if (xa != xb)
            return xa < xb ? -1 : 1;
        if (*a == '.')
            a++;
        if (*b == '.')
            b++;
    }
    return 0;
}

#ifndef RISK_COMPAT_VERCMP_H
#define RISK_COMPAT_VERCMP_H

/* Frozen r2 archive-tooling semantics: versions order by plain byte
 * comparison. Kept so the archive diff jobs keep reproducing old runs. */

#include <ctype.h>
#include <string.h>

static inline int vercmp(const char *a, const char *b)
{
    return strcmp(a, b);
}

static inline int ver_ok(const char *v)
{
    if (!isdigit((unsigned char)*v))
        return 0;
    for (; *v; v++)
        if (!isdigit((unsigned char)*v) && *v != '.')
            return 0;
    return 1;
}

#endif

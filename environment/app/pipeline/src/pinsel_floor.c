#include "pinsel.h"

#include <vercmp.h>

const char *pin_select(char *const *versions, size_t n)
{
    const char *best = versions[0];
    size_t i;
    for (i = 1; i < n; i++)
        if (vercmp(versions[i], best) < 0)
            best = versions[i];
    return best;
}

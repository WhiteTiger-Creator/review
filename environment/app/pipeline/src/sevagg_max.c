#include "sevagg.h"

double sev_aggregate(const double *scores, const char **ids, size_t n)
{
    double best = 0.0;
    size_t i;
    (void)ids;
    for (i = 0; i < n; i++)
        if (scores[i] > best)
            best = scores[i];
    return best;
}

#include "sevagg.h"

#include <string.h>

double sev_aggregate(const double *scores, const char **ids, size_t n)
{
    double best = 0.0, py_best = 0.0;
    int has_py = 0;
    size_t i;
    for (i = 0; i < n; i++) {
        if (scores[i] > best)
            best = scores[i];
        if (strncmp(ids[i], "PYSEC-", 6) == 0) {
            if (!has_py || scores[i] > py_best)
                py_best = scores[i];
            has_py = 1;
        }
    }
    return has_py ? py_best : best;
}

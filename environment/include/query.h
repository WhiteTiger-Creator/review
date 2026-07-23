#ifndef QUERY_H
#define QUERY_H
#include <stdint.h>

typedef struct {
    int k;
    uint64_t *seed;
    double *block;
} PatchSpec;

typedef struct {
    double sigma;
    PatchSpec cond;
    PatchSpec cap;
} CensusCase;

int read_cases(const char *path, CensusCase **cases, int *ncases);
void free_cases(CensusCase *cases, int ncases);
#endif

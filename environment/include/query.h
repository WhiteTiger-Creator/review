#ifndef QUERY_H
#define QUERY_H
#include <stdint.h>

typedef struct {
    double weight;
    uint64_t seed;
} ModSpec;

typedef struct {
    double sigma;
    int k;
    ModSpec *terms;
} QueryCase;

int read_queries(const char *path, QueryCase **cases, int *ncases);
void free_queries(QueryCase *cases, int ncases);
#endif

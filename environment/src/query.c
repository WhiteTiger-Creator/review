#include <stdio.h>
#include <stdlib.h>
#include "query.h"

int read_queries(const char *path, QueryCase **cases, int *ncases) {
    FILE *f = fopen(path, "r");
    if (!f) return 1;
    int q;
    if (fscanf(f, "%d", &q) != 1 || q < 0) { fclose(f); return 2; }
    QueryCase *arr = malloc(sizeof(QueryCase) * (q > 0 ? q : 1));
    if (!arr) { fclose(f); return 3; }
    for (int c = 0; c < q; c++) {
        double sigma; int k;
        if (fscanf(f, "%lf %d", &sigma, &k) != 2 || k < 0) { fclose(f); return 4; }
        arr[c].sigma = sigma;
        arr[c].k = k;
        arr[c].terms = k > 0 ? malloc(sizeof(ModSpec) * k) : NULL;
        for (int i = 0; i < k; i++) {
            double w; unsigned long long s;
            if (fscanf(f, "%lf %llu", &w, &s) != 2) { fclose(f); return 5; }
            arr[c].terms[i].weight = w;
            arr[c].terms[i].seed = (uint64_t)s;
        }
    }
    fclose(f);
    *cases = arr;
    *ncases = q;
    return 0;
}

void free_queries(QueryCase *cases, int ncases) {
    if (!cases) return;
    for (int c = 0; c < ncases; c++) free(cases[c].terms);
    free(cases);
}

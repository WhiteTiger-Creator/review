#include <stdio.h>
#include <stdlib.h>
#include "query.h"

static int read_patch(FILE *f, PatchSpec *p) {
    p->seed = NULL;
    p->block = NULL;
    if (p->k == 0) return 0;
    p->seed = malloc(sizeof(uint64_t) * p->k);
    p->block = malloc(sizeof(double) * p->k * p->k);
    if (!p->seed || !p->block) return 1;
    for (int i = 0; i < p->k; i++) {
        unsigned long long s;
        if (fscanf(f, "%llu", &s) != 1) return 2;
        p->seed[i] = (uint64_t)s;
    }
    for (int i = 0; i < p->k; i++) {
        for (int j = i; j < p->k; j++) {
            double w;
            if (fscanf(f, "%lf", &w) != 1) return 3;
            p->block[i * p->k + j] = w;
            p->block[j * p->k + i] = w;
        }
    }
    return 0;
}

int read_cases(const char *path, CensusCase **cases, int *ncases) {
    FILE *f = fopen(path, "r");
    if (!f) return 1;
    int q;
    if (fscanf(f, "%d", &q) != 1 || q < 0) { fclose(f); return 2; }
    CensusCase *arr = malloc(sizeof(CensusCase) * (q > 0 ? q : 1));
    if (!arr) { fclose(f); return 3; }
    for (int c = 0; c < q; c++) {
        double sigma; int nk, nm;
        if (fscanf(f, "%lf %d %d", &sigma, &nk, &nm) != 3 || nk < 0 || nm < 0) {
            fclose(f); return 4;
        }
        arr[c].sigma = sigma;
        arr[c].cond.k = nk;
        arr[c].cap.k = nm;
        if (read_patch(f, &arr[c].cond) != 0) { fclose(f); return 5; }
        if (read_patch(f, &arr[c].cap) != 0) { fclose(f); return 6; }
    }
    fclose(f);
    *cases = arr;
    *ncases = q;
    return 0;
}

void free_cases(CensusCase *cases, int ncases) {
    if (!cases) return;
    for (int c = 0; c < ncases; c++) {
        free(cases[c].cond.seed);
        free(cases[c].cond.block);
        free(cases[c].cap.seed);
        free(cases[c].cap.block);
    }
    free(cases);
}

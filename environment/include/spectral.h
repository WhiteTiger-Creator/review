#ifndef SPECTRAL_H
#define SPECTRAL_H

typedef struct {
    int n;
    long nnz;
    int *ii;
    int *jj;
    double *vv;
} SymCoo;

typedef struct {
    int k;
    double **vec;
    double *block;
} PatchSet;

long count_modes_below(const SymCoo *cond, double sigma,
                       const PatchSet *cpatch, const PatchSet *mpatch);

#endif

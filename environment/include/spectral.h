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
    double weight;
    double *vec;
} RankOneMod;

long count_eig_below(const SymCoo *op, double sigma, const RankOneMod *mods, int nmods);

#endif

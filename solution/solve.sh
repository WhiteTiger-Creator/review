#!/usr/bin/env bash
set -euo pipefail
cd /app

WORK="$(mktemp -d)"
curl -fsSL --retry 3 -o "$WORK/op.tar.gz" "https://sparse.tamu.edu/MM/Schmid/thermal2.tar.gz" \
  || curl -fsSL --retry 3 -o "$WORK/op.tar.gz" "https://suitesparse-collection-website.herokuapp.com/MM/Schmid/thermal2.tar.gz"
echo "02934a4b642b6829c33517e0b801b60ea894a6552c6cd7e3db6c709c776434ce  $WORK/op.tar.gz" | sha256sum -c -
tar xzf "$WORK/op.tar.gz" -C "$WORK"
mv "$WORK/thermal2/thermal2.mtx" /app/operator.mtx
rm -rf "$WORK"

cat > src/counter.c <<'CEOF'
#include <stdlib.h>
#include <string.h>
#include "spectral.h"
#include "dmumps_c.h"
#define USE_COMM_WORLD -987654

extern void dsyev_(char *, char *, int *, double *, int *, double *, double *, int *, int *);

static int neg_eig_sym(double *S, int k) {
    if (k == 0) return 0;
    double *w = malloc(sizeof(double) * k);
    int lwork = 8 * k + 16, info;
    double *work = malloc(sizeof(double) * lwork);
    char jz = 'N', ul = 'U';
    dsyev_(&jz, &ul, &k, S, &k, w, work, &lwork, &info);
    int c = 0;
    for (int i = 0; i < k; i++) if (w[i] < 0.0) c++;
    free(w); free(work);
    return c;
}

long count_eig_below(const SymCoo *op, double sigma, const RankOneMod *mods, int nmods) {
    int n = op->n;
    long base = op->nnz;
    long nz = base + n;
    int *irn = malloc(sizeof(int) * nz);
    int *jcn = malloc(sizeof(int) * nz);
    double *a = malloc(sizeof(double) * nz);
    for (long e = 0; e < base; e++) {
        irn[e] = op->ii[e] + 1;
        jcn[e] = op->jj[e] + 1;
        a[e] = op->vv[e];
    }
    for (int i = 0; i < n; i++) {
        irn[base + i] = i + 1;
        jcn[base + i] = i + 1;
        a[base + i] = -sigma;
    }

    DMUMPS_STRUC_C id;
    id.comm_fortran = USE_COMM_WORLD;
    id.par = 1;
    id.sym = 2;
    id.job = -1;
    dmumps_c(&id);
    id.n = n;
    id.nz = (int)nz;
    id.irn = irn;
    id.jcn = jcn;
    id.a = a;
    id.icntl[0] = -1;
    id.icntl[1] = -1;
    id.icntl[2] = -1;
    id.icntl[3] = 0;
    id.job = 4;
    dmumps_c(&id);
    if (id.infog[0] < 0) {
        id.job = -2;
        dmumps_c(&id);
        free(irn); free(jcn); free(a);
        return -999999999L;
    }
    int negK = id.infog[11];

    long count = negK;
    if (nmods > 0) {
        int k = nmods;
        double *rhs = malloc(sizeof(double) * (size_t)n * k);
        for (int p = 0; p < k; p++)
            memcpy(rhs + (size_t)p * n, mods[p].vec, sizeof(double) * n);
        id.nrhs = k;
        id.lrhs = n;
        id.rhs = rhs;
        id.job = 3;
        dmumps_c(&id);

        double *S = malloc(sizeof(double) * k * k);
        for (int p = 0; p < k; p++)
            for (int q = 0; q < k; q++) {
                double utx = 0.0;
                for (int i = 0; i < n; i++)
                    utx += mods[p].vec[i] * rhs[(size_t)q * n + i];
                double diag = (p == q) ? (-1.0 / mods[p].weight) : 0.0;
                S[p * k + q] = diag - utx;
            }
        int negS = neg_eig_sym(S, k);
        int negDblock = 0;
        for (int p = 0; p < k; p++) if (mods[p].weight > 0.0) negDblock++;
        count = (long)negK + negS - negDblock;
        free(S);
        free(rhs);
    }

    id.job = -2;
    dmumps_c(&id);
    free(irn); free(jcn); free(a);
    return count;
}
CEOF

make
echo "oracle build complete"

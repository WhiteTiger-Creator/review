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
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include "spectral.h"
#include "dmumps_c.h"
#define USE_COMM_WORLD -987654

extern void dsyev_(char *, char *, int *, double *, int *, double *, double *, int *, int *);
extern void dgesv_(int *, int *, double *, int *, int *, double *, int *, int *);

static int neg_count_sym(const double *A, int k) {
    if (k <= 0) return 0;
    double *W = malloc(sizeof(double) * (size_t)k * k);
    memcpy(W, A, sizeof(double) * (size_t)k * k);
    double *w = malloc(sizeof(double) * k);
    int lwork = 16 * k + 64, info = 0;
    double *work = malloc(sizeof(double) * lwork);
    char jz = 'N', ul = 'U';
    int kk = k;
    dsyev_(&jz, &ul, &kk, W, &kk, w, work, &lwork, &info);
    int c = 0;
    for (int i = 0; i < k; i++) if (w[i] < 0.0) c++;
    free(W); free(w); free(work);
    return c;
}

static void invert_sym(const double *A, double *out, int k) {
    double *M = malloc(sizeof(double) * (size_t)k * k);
    memcpy(M, A, sizeof(double) * (size_t)k * k);
    for (int i = 0; i < k; i++)
        for (int j = 0; j < k; j++)
            out[i * k + j] = (i == j) ? 1.0 : 0.0;
    int *ipiv = malloc(sizeof(int) * k);
    int kk = k, info = 0;
    dgesv_(&kk, &kk, M, &kk, ipiv, out, &kk, &info);
    for (int i = 0; i < k; i++)
        for (int j = i + 1; j < k; j++) {
            double s = 0.5 * (out[i * k + j] + out[j * k + i]);
            out[i * k + j] = s;
            out[j * k + i] = s;
        }
    free(M); free(ipiv);
}

long count_modes_below(const SymCoo *cond, double sigma,
                       const PatchSet *cpatch, const PatchSet *mpatch) {
    int n = cond->n;
    long stored = cond->nnz;

    double *rowabs = calloc((size_t)n, sizeof(double));
    double *diag = calloc((size_t)n, sizeof(double));
    for (long e = 0; e < stored; e++) {
        int i = cond->ii[e], j = cond->jj[e];
        double v = cond->vv[e];
        double av = fabs(v);
        if (i == j) {
            rowabs[i] += av;
            diag[i] += v;
        } else {
            rowabs[i] += av;
            rowabs[j] += av;
        }
    }

    long off = 0;
    for (long e = 0; e < stored; e++) if (cond->ii[e] != cond->jj[e]) off++;
    long nz = off + n;
    int *irn = malloc(sizeof(int) * (size_t)nz);
    int *jcn = malloc(sizeof(int) * (size_t)nz);
    double *a = malloc(sizeof(double) * (size_t)nz);
    long p = 0;
    for (long e = 0; e < stored; e++) {
        int i = cond->ii[e], j = cond->jj[e];
        if (i == j) continue;
        double v = cond->vv[e];
        irn[p] = i + 1;
        jcn[p] = j + 1;
        a[p] = v - sigma * fabs(v);
        p++;
    }
    for (int i = 0; i < n; i++) {
        irn[p] = i + 1;
        jcn[p] = i + 1;
        a[p] = diag[i] - sigma * rowabs[i];
        p++;
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
        free(irn); free(jcn); free(a); free(rowabs); free(diag);
        return -999999999L;
    }
    long census = id.infog[11];

    int nk = cpatch ? cpatch->k : 0;
    int nm = mpatch ? mpatch->k : 0;
    int kt = nk + nm;
    if (kt > 0) {
        double *G = calloc((size_t)kt * kt, sizeof(double));
        for (int i = 0; i < nk; i++)
            for (int j = 0; j < nk; j++)
                G[i * kt + j] = cpatch->block[i * nk + j];
        for (int i = 0; i < nm; i++)
            for (int j = 0; j < nm; j++)
                G[(nk + i) * kt + (nk + j)] = -sigma * mpatch->block[i * nm + j];

        double *U = malloc(sizeof(double) * (size_t)n * kt);
        for (int c = 0; c < nk; c++)
            memcpy(U + (size_t)c * n, cpatch->vec[c], sizeof(double) * n);
        for (int c = 0; c < nm; c++)
            memcpy(U + (size_t)(nk + c) * n, mpatch->vec[c], sizeof(double) * n);

        double *X = malloc(sizeof(double) * (size_t)n * kt);
        memcpy(X, U, sizeof(double) * (size_t)n * kt);
        id.nrhs = kt;
        id.lrhs = n;
        id.rhs = X;
        id.job = 3;
        dmumps_c(&id);

        double *Ginv = malloc(sizeof(double) * (size_t)kt * kt);
        invert_sym(G, Ginv, kt);

        double *S = malloc(sizeof(double) * (size_t)kt * kt);
        for (int i = 0; i < kt; i++) {
            for (int j = 0; j < kt; j++) {
                double t = 0.0;
                const double *ui = U + (size_t)i * n;
                const double *xj = X + (size_t)j * n;
                for (int r = 0; r < n; r++) t += ui[r] * xj[r];
                S[i * kt + j] = -Ginv[i * kt + j] - t;
            }
        }
        for (int i = 0; i < kt; i++)
            for (int j = i + 1; j < kt; j++) {
                double s = 0.5 * (S[i * kt + j] + S[j * kt + i]);
                S[i * kt + j] = s;
                S[j * kt + i] = s;
            }

        double *negG = malloc(sizeof(double) * (size_t)kt * kt);
        for (int i = 0; i < kt * kt; i++) negG[i] = -G[i];

        census += neg_count_sym(S, kt);
        census -= neg_count_sym(negG, kt);

        free(G); free(U); free(X); free(Ginv); free(S); free(negG);
    }

    id.job = -2;
    dmumps_c(&id);
    free(irn); free(jcn); free(a); free(rowabs); free(diag);
    return census;
}
CEOF

make
echo "oracle build complete"

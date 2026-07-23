#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mtxread.h"

int read_symmetric_mtx(const char *path, SymCoo *out) {
    FILE *f = fopen(path, "r");
    if (!f) return 1;
    char line[512];
    do {
        if (!fgets(line, sizeof(line), f)) { fclose(f); return 2; }
    } while (line[0] == '%');
    long nr, nc, nz;
    if (sscanf(line, "%ld %ld %ld", &nr, &nc, &nz) != 3) { fclose(f); return 3; }
    if (nr != nc) { fclose(f); return 4; }
    int *ii = malloc(sizeof(int) * nz);
    int *jj = malloc(sizeof(int) * nz);
    double *vv = malloc(sizeof(double) * nz);
    if (!ii || !jj || !vv) { fclose(f); return 5; }
    long got = 0;
    for (long e = 0; e < nz; e++) {
        long i, j; double v;
        if (fscanf(f, "%ld %ld %lf", &i, &j, &v) != 3) { fclose(f); return 6; }
        ii[got] = (int)(i - 1);
        jj[got] = (int)(j - 1);
        vv[got] = v;
        got++;
    }
    fclose(f);
    out->n = (int)nr;
    out->nnz = got;
    out->ii = ii;
    out->jj = jj;
    out->vv = vv;
    return 0;
}

void free_symcoo(SymCoo *m) {
    if (!m) return;
    free(m->ii); free(m->jj); free(m->vv);
    m->ii = NULL; m->jj = NULL; m->vv = NULL;
}

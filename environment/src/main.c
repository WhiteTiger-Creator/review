#include <stdio.h>
#include <stdlib.h>
#include "spectral.h"
#include "mtxread.h"
#include "vecgen.h"
#include "query.h"

static void build_set(const PatchSpec *spec, int n, PatchSet *set) {
    set->k = spec->k;
    set->block = spec->block;
    set->vec = NULL;
    if (spec->k == 0) return;
    set->vec = malloc(sizeof(double *) * spec->k);
    for (int i = 0; i < spec->k; i++) {
        set->vec[i] = malloc(sizeof(double) * n);
        fill_mode_vector(spec->seed[i], set->vec[i], n);
    }
}

static void drop_set(PatchSet *set) {
    for (int i = 0; i < set->k; i++) free(set->vec[i]);
    free(set->vec);
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s <operator.mtx> <case_file>\n", argv[0]);
        return 2;
    }
    SymCoo cond;
    if (read_symmetric_mtx(argv[1], &cond) != 0) {
        fprintf(stderr, "error: could not read operator from %s\n", argv[1]);
        return 3;
    }
    CensusCase *cases; int nc;
    if (read_cases(argv[2], &cases, &nc) != 0) {
        fprintf(stderr, "error: could not read cases from %s\n", argv[2]);
        return 4;
    }
    for (int c = 0; c < nc; c++) {
        PatchSet cp, mp;
        build_set(&cases[c].cond, cond.n, &cp);
        build_set(&cases[c].cap, cond.n, &mp);
        long cnt = count_modes_below(&cond, cases[c].sigma, &cp, &mp);
        printf("%ld\n", cnt);
        fflush(stdout);
        drop_set(&cp);
        drop_set(&mp);
    }
    free_cases(cases, nc);
    free_symcoo(&cond);
    return 0;
}

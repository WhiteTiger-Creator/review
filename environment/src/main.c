#include <stdio.h>
#include <stdlib.h>
#include "spectral.h"
#include "mtxread.h"
#include "vecgen.h"
#include "query.h"

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s <operator.mtx> <query_file>\n", argv[0]);
        return 2;
    }
    SymCoo op;
    if (read_symmetric_mtx(argv[1], &op) != 0) {
        fprintf(stderr, "error: could not read operator from %s\n", argv[1]);
        return 3;
    }
    QueryCase *cases; int nc;
    if (read_queries(argv[2], &cases, &nc) != 0) {
        fprintf(stderr, "error: could not read queries from %s\n", argv[2]);
        return 4;
    }
    for (int c = 0; c < nc; c++) {
        QueryCase *q = &cases[c];
        RankOneMod *mods = q->k > 0 ? malloc(sizeof(RankOneMod) * q->k) : NULL;
        for (int i = 0; i < q->k; i++) {
            mods[i].weight = q->terms[i].weight;
            mods[i].vec = malloc(sizeof(double) * op.n);
            fill_mode_vector(q->terms[i].seed, mods[i].vec, op.n);
        }
        long cnt = count_eig_below(&op, q->sigma, mods, q->k);
        printf("%ld\n", cnt);
        for (int i = 0; i < q->k; i++) free(mods[i].vec);
        free(mods);
    }
    free_queries(cases, nc);
    free_symcoo(&op);
    return 0;
}

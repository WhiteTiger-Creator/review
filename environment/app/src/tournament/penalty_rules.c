#include "qr_composer.h"

/* Mask penalty scorers used by run-mask-tournament.
 * N1 adjacent runs, N2 2x2 blocks, N3 finder-like patterns, N4 dark balance. */

int qrt_penalty_runs(const qrt_matrix *m) {
    int size = m->size;
    int total = 0;
    for (int axis = 0; axis < 2; axis++) {
        for (int a = 0; a < size; a++) {
            int run = 1;
            for (int b = 1; b < size; b++) {
                int cur = axis == 0 ? m->grid[a][b] : m->grid[b][a];
                int prev = axis == 0 ? m->grid[a][b - 1] : m->grid[b - 1][a];
                if (cur == prev) {
                    run++;
                } else {
                    if (run >= 5) total += 3 + (run - 5);
                    run = 1;
                }
            }
            if (run >= 5) total += 3 + (run - 5);
        }
    }
    return total;
}

int qrt_penalty_blocks(const qrt_matrix *m) {
    int size = m->size;
    int total = 0;
    for (int r = 0; r < size - 1; r++) {
        for (int c = 0; c < size - 1; c++) {
            int v = m->grid[r][c];
            if (m->grid[r][c + 1] == v && m->grid[r + 1][c] == v && m->grid[r + 1][c + 1] == v)
                total += 3;
        }
    }
    return total;
}

static const uint8_t FINDER_CORE[7] = {1, 0, 1, 1, 1, 0, 1};

int qrt_penalty_finder(const qrt_matrix *m) {
    int size = m->size;
    int total = 0;
    for (int axis = 0; axis < 2; axis++) {
        for (int a = 0; a < size; a++) {
            for (int i = 0; i + 7 <= size; i++) {
                int match = 1;
                for (int k = 0; k < 7; k++) {
                    int v = axis == 0 ? m->grid[a][i + k] : m->grid[i + k][a];
                    if (v != FINDER_CORE[k]) {
                        match = 0;
                        break;
                    }
                }
                if (match) total += 40;
            }
        }
    }
    return total;
}

int qrt_penalty_balance(const qrt_matrix *m) {
    int size = m->size;
    int dark = 0;
    for (int r = 0; r < size; r++)
        for (int c = 0; c < size; c++) dark += m->grid[r][c];
    int total = size * size;
    int diff = 20 * dark - 10 * total;
    if (diff < 0) diff = -diff;
    int k = diff / total;
    return 10 * k;
}

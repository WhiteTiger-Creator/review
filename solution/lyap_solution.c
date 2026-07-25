#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

static int cmp_str(const void *a, const void *b) {
    return strcmp(*(const char **)a, *(const char **)b);
}

static int has_suffix(const char *s, const char *suf) {
    size_t ls = strlen(s), lf = strlen(suf);
    return ls >= lf && strcmp(s + ls - lf, suf) == 0;
}

static int cmp_desc(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x < y) - (x > y);
}

/* Householder QR of the n-by-n matrix B = Qb * R. Writes the fresh orthonormal
 * factor Qb (identity-initialized) and the full upper-triangular R. B destroyed. */
static void qr_step(int n, double *B, double *Q, double *R) {
    for (int i = 0; i < n * n; i++) Q[i] = 0.0;
    for (int i = 0; i < n; i++) Q[i * n + i] = 1.0;
    for (int j = 0; j < n; j++) {
        double nrm = 0.0;
        for (int i = j; i < n; i++) nrm += B[i * n + j] * B[i * n + j];
        nrm = sqrt(nrm);
        if (nrm == 0.0) continue;
        double *v = (double *)calloc(n, sizeof(double));
        double x0 = B[j * n + j];
        double alpha = (x0 >= 0.0 ? -nrm : nrm);
        for (int i = j; i < n; i++) v[i] = B[i * n + j];
        v[j] -= alpha;
        double vn = 0.0;
        for (int i = j; i < n; i++) vn += v[i] * v[i];
        if (vn == 0.0) { free(v); continue; }
        for (int c = j; c < n; c++) {
            double dot = 0.0;
            for (int i = j; i < n; i++) dot += v[i] * B[i * n + c];
            double f = 2.0 * dot / vn;
            for (int i = j; i < n; i++) B[i * n + c] -= f * v[i];
        }
        for (int r = 0; r < n; r++) {
            double dot = 0.0;
            for (int i = j; i < n; i++) dot += Q[r * n + i] * v[i];
            double f = 2.0 * dot / vn;
            for (int i = j; i < n; i++) Q[r * n + i] -= f * v[i];
        }
        free(v);
    }
    for (int i = 0; i < n; i++)
        for (int j = 0; j < n; j++)
            R[i * n + j] = (j >= i) ? B[i * n + j] : 0.0;
}

/* One-sided Jacobi SVD: orthogonalize the columns of A (n-by-n, row-major),
 * returning the singular values (column norms after convergence) in sv.
 * A is overwritten. Achieves high relative accuracy on graded matrices. */
static void one_sided_jacobi(int n, double *A, double *sv) {
    for (int sweep = 0; sweep < 200; sweep++) {
        double off = 0.0;
        for (int p = 0; p < n - 1; p++) {
            for (int q = p + 1; q < n; q++) {
                double app = 0.0, aqq = 0.0, apq = 0.0;
                for (int i = 0; i < n; i++) {
                    double aip = A[i * n + p], aiq = A[i * n + q];
                    app += aip * aip;
                    aqq += aiq * aiq;
                    apq += aip * aiq;
                }
                if (app == 0.0 || aqq == 0.0) continue;
                double rel = fabs(apq) / sqrt(app * aqq);
                if (rel > off) off = rel;
                if (fabs(apq) <= 1e-300) continue;
                double tau = (aqq - app) / (2.0 * apq);
                double t = (tau == 0.0) ? 1.0
                    : ((tau > 0.0 ? 1.0 : -1.0) / (fabs(tau) + sqrt(1.0 + tau * tau)));
                double c = 1.0 / sqrt(1.0 + t * t);
                double s = c * t;
                for (int i = 0; i < n; i++) {
                    double aip = A[i * n + p], aiq = A[i * n + q];
                    A[i * n + p] = c * aip - s * aiq;
                    A[i * n + q] = s * aip + c * aiq;
                }
            }
        }
        if (off < 1e-15) break;
    }
    for (int j = 0; j < n; j++) {
        double s = 0.0;
        for (int i = 0; i < n; i++) s += A[i * n + j] * A[i * n + j];
        sv[j] = sqrt(s);
    }
}

static void solve_one(const char *path, FILE *out, const char *name) {
    FILE *in = fopen(path, "r");
    if (!in) return;
    int n = 0, k = 0;
    if (fscanf(in, "%d %d", &n, &k) != 2) { fclose(in); return; }
    double *Q = (double *)malloc(sizeof(double) * n * n);
    double *B = (double *)malloc(sizeof(double) * n * n);
    double *A = (double *)malloc(sizeof(double) * n * n);
    double *R = (double *)malloc(sizeof(double) * n * n);
    double *U = (double *)calloc(n * n, sizeof(double));
    double *Un = (double *)malloc(sizeof(double) * n * n);
    double *At = (double *)malloc(sizeof(double) * n * n);
    double *sv = (double *)malloc(sizeof(double) * n);
    double *exps = (double *)malloc(sizeof(double) * n);
    for (int i = 0; i < n * n; i++) Q[i] = 0.0;
    for (int i = 0; i < n; i++) Q[i * n + i] = 1.0;
    for (int i = 0; i < n; i++) U[i * n + i] = 1.0;
    int ok = 1;
    for (int step = 0; step < k && ok; step++) {
        for (int t = 0; t < n * n; t++)
            if (fscanf(in, "%lf", &A[t]) != 1) { ok = 0; break; }
        if (!ok) break;
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++) {
                double s = 0.0;
                for (int t = 0; t < n; t++) s += A[i * n + t] * Q[t * n + j];
                B[i * n + j] = s;
            }
        qr_step(n, B, Q, R);
        /* U <- R * U (both upper-triangular; result upper-triangular) */
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++) {
                double s = 0.0;
                for (int t = i; t <= j && t < n; t++) s += R[i * n + t] * U[t * n + j];
                Un[i * n + j] = s;
            }
        double *tmp = U; U = Un; Un = tmp;
    }
    fclose(in);
    if (ok) {
        /* singular values of P equal singular values of U (P = Q_k U). Get them
         * with high relative accuracy by one-sided Jacobi on A = U^T. */
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++) At[i * n + j] = U[j * n + i];
        one_sided_jacobi(n, At, sv);
        for (int j = 0; j < n; j++) exps[j] = log(sv[j]) / (double)k;
        qsort(exps, n, sizeof(double), cmp_desc);
        fprintf(out, "%s", name);
        for (int j = 0; j < n; j++) fprintf(out, " %.17g", exps[j]);
        fprintf(out, "\n");
    }
    free(Q); free(B); free(A); free(R); free(U); free(Un);
    free(At); free(sv); free(exps);
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s <input_dir> <output_path>\n", argv[0]);
        return 2;
    }
    DIR *d = opendir(argv[1]);
    if (!d) { fprintf(stderr, "cannot open input dir\n"); return 2; }
    char **names = NULL;
    size_t count = 0, cap = 0;
    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        if (!has_suffix(e->d_name, ".txt")) continue;
        if (has_suffix(e->d_name, ".expected.txt")) continue;
        if (count == cap) { cap = cap ? cap * 2 : 16; names = realloc(names, cap * sizeof(char *)); }
        names[count++] = strdup(e->d_name);
    }
    closedir(d);
    qsort(names, count, sizeof(char *), cmp_str);
    FILE *out = fopen(argv[2], "w");
    if (!out) { fprintf(stderr, "cannot open output\n"); return 2; }
    for (size_t i = 0; i < count; i++) {
        char path[4096];
        snprintf(path, sizeof(path), "%s/%s", argv[1], names[i]);
        solve_one(path, out, names[i]);
        free(names[i]);
    }
    fclose(out);
    free(names);
    return 0;
}
